"""Extracción de (nombre, teléfono) desde una foto de planilla de turnos, vía Tesseract local.

No pretende ser precisa: la tabla de revisión en la UI compensa los errores de OCR. La idea es
un candidato razonable por persona, no un parseo perfecto de la hoja.
"""
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageOps

from db import FilaImport

RE_NOMBRE = re.compile(r"\b[A-ZÁÉÍÓÚÑ]{2,}(?:\s+[A-ZÁÉÍÓÚÑ]{2,}){1,4}\b")
RE_SOLO_NUMERICO = re.compile(r"[\d\s\-]+")

# Palabras sueltas de 2-3 letras que dan falsos positivos como "nombre" (títulos, negaciones)
# pero NO deben bloquear prefijos de apellido reales como "DI SANTO" o "DA SILVA": el filtro
# solo descarta el match si la PRIMERA palabra es una de éstas, no si aparece en el medio.
PALABRAS_NO_NOMBRE = {"DR", "DRA", "SR", "SRA", "N", "NO", "SI", "ART"}

# Si una línea entera contiene alguna de estas palabras, es una línea de encabezado/metadata
# de la planilla (el profesional que atiende, la institución, la fecha, etc.) y no un
# paciente — aunque tenga un nombre en mayúsculas adentro (ej. "Profesional: MUSSINI DANIEL").
LINEA_NO_PACIENTE = [
    "profesional",
    "institucion",
    "ubicacion",
    "turnos asignados",
    "solicitud",
    "ope. servicio",
    "ope servicio",
    "apellido y nombre",
    "hoja nro",
]

LINEAS_DE_BUSQUEDA_TELEFONO = 2  # además de la línea del nombre, busca en las próximas N
MAX_PALABRAS_POR_TELEFONO = 3  # cuántos tokens consecutivos se combinan como candidato
UMBRAL_CONFIANZA_PARA_REFINAR = 70  # 0-100: por debajo de esto, vale la pena intentar el
# recorte+whitelist; por encima, la pasada general ya viene bien y no conviene arriesgarla.
UMBRAL_CONFIANZA_AVISO = 60  # por debajo de esto, la fila se marca para revisión en la UI


class TesseractNoDisponible(Exception):
    pass


_ultimo_uso_idioma_default = False  # True si la última extracción tuvo que caer a inglés


def hubo_fallback_idioma() -> bool:
    """True si la última llamada a extraer_candidatos() no pudo usar español y cayó al
    idioma por defecto de Tesseract (inglés) — la UI usa esto para avisar en vez de mostrar
    resultados malos sin explicación."""
    return _ultimo_uso_idioma_default


def _configurar_tesseract_embebido(pytesseract) -> None:
    """Cuando la app corre empaquetada (.exe de PyInstaller), el build en GitHub Actions
    empaqueta el propio Tesseract-OCR adentro del ejecutable (ver .github/workflows/build.yml)
    para que no haga falta instalarlo aparte en la PC de destino. Acá lo detectamos y le
    decimos a pytesseract que use ESE binario en vez de buscar uno en el sistema.
    En modo desarrollo (`python main.py`), sys.frozen no existe y esto no hace nada: sigue
    usando el Tesseract del sistema, como documenta el README."""
    if not getattr(sys, "frozen", False):
        return
    base = Path(getattr(sys, "_MEIPASS", ""))
    tesseract_exe = base / "tesseract" / "tesseract.exe"
    tessdata_dir = base / "tesseract" / "tessdata"
    if tesseract_exe.exists():
        pytesseract.pytesseract.tesseract_cmd = str(tesseract_exe)
    if tessdata_dir.exists():
        # OJO: la ruta se pasa SOLO por TESSDATA_PREFIX. Antes también se agregaba
        # `--tessdata-dir "<ruta>"` al config, pero en Windows pytesseract corta el config con
        # shlex(posix=False), que NO saca las comillas: Tesseract recibía la ruta con comillas
        # literales adentro y no podía abrir ningún idioma ("no se pudo cargar ningún idioma").
        os.environ["TESSDATA_PREFIX"] = str(tessdata_dir)


def _requerir_pytesseract():
    try:
        import pytesseract
    except ImportError as exc:
        raise TesseractNoDisponible(
            "Falta instalar la librería pytesseract (pip install pytesseract)."
        ) from exc
    _configurar_tesseract_embebido(pytesseract)
    return pytesseract


def preprocesar_imagen(path: str) -> Image.Image:
    img = Image.open(path).convert("L")  # escala de grises

    # Upscale si la imagen es chica, ayuda a Tesseract con fuentes pequeñas
    if max(img.size) < 1600:
        factor = 1600 / max(img.size)
        img = img.resize((int(img.width * factor), int(img.height * factor)), Image.LANCZOS)

    img = ImageOps.autocontrast(img)
    img = _deskew(img)
    # No binarizamos: validado contra fotos reales, Tesseract con su propia binarización
    # adaptativa interna lee mejor que forzando nosotros un threshold fijo.
    return img


def _proyeccion_horizontal(img: Image.Image) -> float:
    """Varianza del conteo de píxeles oscuros por fila: más alta cuando el texto está derecho
    (las líneas de texto se alinean horizontalmente)."""
    pixeles = img.load()
    w, h = img.size
    conteos = []
    for y in range(0, h, 2):  # cada 2 filas para no recorrer todo, alcanza para estimar
        oscuros = sum(1 for x in range(0, w, 2) if pixeles[x, y] < 128)
        conteos.append(oscuros)
    n = len(conteos)
    if n == 0:
        return 0.0
    media = sum(conteos) / n
    return sum((c - media) ** 2 for c in conteos) / n


def _deskew(img: Image.Image, rango: float = 8.0, paso: float = 1.0) -> Image.Image:
    """Prueba ángulos chicos y se queda con el que da mayor varianza en la proyección
    horizontal (texto más "alineado"). Trabaja sobre una copia reducida para que sea rápido,
    y aplica el ángulo encontrado a la imagen original."""
    miniatura = img.copy()
    miniatura.thumbnail((300, 300))

    mejor_angulo = 0.0
    mejor_score = -1.0
    angulo = -rango
    while angulo <= rango:
        rotada = miniatura.rotate(angulo, expand=False, fillcolor=255)
        score = _proyeccion_horizontal(rotada)
        if score > mejor_score:
            mejor_score = score
            mejor_angulo = angulo
        angulo += paso

    if abs(mejor_angulo) < 0.5:
        return img
    return img.rotate(mejor_angulo, expand=True, fillcolor=255)


@dataclass
class _Palabra:
    texto: str
    left: int
    top: int
    width: int
    height: int
    conf: float
    line_key: tuple

    @property
    def right(self) -> int:
        return self.left + self.width

    @property
    def bottom(self) -> int:
        return self.top + self.height


TESSERACT_CONFIG = "--psm 6"  # asume un único bloque de texto uniforme: mucho mejor para
# planillas tabulares fotografiadas que el modo automático de Tesseract (psm 3, pensado para
# páginas de texto corrido), que en pruebas reales perdía filas enteras de la tabla.


def _extraer_palabras(img: Image.Image) -> list[_Palabra]:
    global _ultimo_uso_idioma_default
    _ultimo_uso_idioma_default = False
    pytesseract = _requerir_pytesseract()
    config = TESSERACT_CONFIG
    try:
        data = pytesseract.image_to_data(
            img, lang="spa", config=config, output_type=pytesseract.Output.DICT
        )
    except pytesseract.TesseractNotFoundError as exc:
        raise TesseractNoDisponible(
            "No se encontró Tesseract-OCR instalado en el sistema.\n\n"
            "Descargalo de https://github.com/UB-Mannheim/tesseract/wiki (instalador para "
            "Windows) y asegurate de agregarlo al PATH durante la instalación."
        ) from exc
    except Exception:
        # lang="spa" puede no estar instalado (o no poder cargarse); reintentamos con el
        # idioma por defecto y dejamos constancia para que la UI pueda avisar.
        _ultimo_uso_idioma_default = True
        try:
            data = pytesseract.image_to_data(
                img, config=config, output_type=pytesseract.Output.DICT
            )
        except Exception as exc:
            # Ni español ni el idioma por defecto pudieron cargar: la instalación de
            # Tesseract-OCR (o su tessdata) está rota o incompleta. Antes esto se dejaba
            # escapar sin capturar y la UI terminaba mostrando la excepción cruda de
            # pytesseract (ej. "(1, 'Error opening data file ...')"), ilegible para alguien
            # sin conocimientos técnicos.
            raise TesseractNoDisponible(
                "No se pudo cargar ningún idioma de reconocimiento de texto (ni español ni "
                "el idioma por defecto). Puede ser un problema con la instalación de "
                "Tesseract-OCR: si estás en el .exe empaquetado, probá reinstalarlo desde un "
                "Release más reciente; si tenés Tesseract instalado aparte, revisá que la "
                "carpeta \"tessdata\" tenga los archivos de idioma."
            ) from exc

    palabras = []
    n = len(data.get("text", []))
    for i in range(n):
        texto = (data["text"][i] or "").strip()
        if not texto:
            continue
        line_key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
        try:
            conf = float(data["conf"][i])
        except (ValueError, TypeError):
            conf = -1.0
        palabras.append(
            _Palabra(
                texto=texto,
                left=data["left"][i],
                top=data["top"][i],
                width=data["width"][i],
                height=data["height"][i],
                conf=conf,
                line_key=line_key,
            )
        )
    return palabras


def _agrupar_lineas(palabras: list[_Palabra]) -> list[list[_Palabra]]:
    lineas: dict[tuple, list[_Palabra]] = {}
    orden: list[tuple] = []
    for p in palabras:
        if p.line_key not in lineas:
            lineas[p.line_key] = []
            orden.append(p.line_key)
        lineas[p.line_key].append(p)
    return [lineas[k] for k in orden]


def _limpiar_telefono(candidato: str) -> str:
    return candidato.replace(" ", "").replace("-", "")


def _candidatos_telefono_en_linea(
    linea: list["_Palabra"],
) -> list[tuple[str, int, list["_Palabra"]]]:
    """Busca teléfonos combinando hasta MAX_PALABRAS_POR_TELEFONO tokens *consecutivos* que
    sean puramente numéricos (dígitos/espacios/guiones). Trabajar por token en vez de sobre
    el texto de toda la línea evita que un teléfono y un número de otra columna (ficha, DNI)
    que quedan separados solo por un espacio en la línea de Tesseract se peguen en un único
    número falso. Devuelve (teléfono_limpio, x_izquierda_del_primer_token, palabras_fuente)."""
    candidatos = []
    n = len(linea)
    for i in range(n):
        for span in range(1, MAX_PALABRAS_POR_TELEFONO + 1):
            if i + span > n:
                break
            tramo = linea[i : i + span]
            if not all(RE_SOLO_NUMERICO.fullmatch(p.texto) for p in tramo):
                break  # si un token no es numérico, ni éste ni los que siguen extienden el candidato
            limpio = _limpiar_telefono(" ".join(p.texto for p in tramo))
            if 6 <= len(limpio) <= 11:
                candidatos.append((limpio, tramo[0].left, tramo))

    # si un candidato es sub-cadena de otro más largo (ej. "500292" dentro de "155500292",
    # porque el teléfono venía partido en 2 tokens de Tesseract), nos quedamos con el más
    # largo: el corto es solo un fragmento del mismo número, no un candidato independiente.
    return [
        (limpio, x, tramo)
        for limpio, x, tramo in candidatos
        if not any(limpio != otro and limpio in otro for otro, _, _ in candidatos)
    ]


ALFABETO_NOMBRE = "ABCDEFGHIJKLMNÑOPQRSTUVWXYZÁÉÍÓÚ "
DIGITOS_TELEFONO = "0123456789- "


def _recortar_y_refinar(img: Image.Image, palabras: list["_Palabra"], whitelist: str) -> str:
    """Recorta el rectángulo que ocupan estas palabras (con margen) y corre Tesseract SOLO
    ahí, restringido a `whitelist`. Al no tener que decidir entre letras y dígitos en toda la
    hoja, Tesseract se confunde mucho menos en esa región puntual que en la pasada general."""
    if not palabras:
        return ""
    pytesseract = _requerir_pytesseract()
    margen = 4
    x0 = max(0, min(p.left for p in palabras) - margen)
    y0 = max(0, min(p.top for p in palabras) - margen)
    x1 = min(img.width, max(p.right for p in palabras) + margen)
    y1 = min(img.height, max(p.bottom for p in palabras) + margen)
    if x1 <= x0 or y1 <= y0:
        return ""
    recorte = img.crop((x0, y0, x1, y1))
    config = f"--psm 7 -c tessedit_char_whitelist={whitelist}"
    try:
        return pytesseract.image_to_string(recorte, lang="spa", config=config).strip()
    except Exception:  # noqa: BLE001 - si falla el refinamiento, seguimos con lo que ya había
        return ""


def _promedio_confianza(palabras: list["_Palabra"]) -> float:
    confs = [p.conf for p in palabras if p.conf >= 0]
    return sum(confs) / len(confs) if confs else -1.0


def extraer_candidatos(path: str) -> list[FilaImport]:
    """Devuelve una FilaImport por cada par (nombre, teléfono) detectado. No lanza si no
    encuentra nada: devuelve lista vacía."""
    img = preprocesar_imagen(path)
    palabras = _extraer_palabras(img)
    lineas = _agrupar_lineas(palabras)

    candidatos: list[FilaImport] = []
    for i, linea in enumerate(lineas):
        texto_linea = " ".join(p.texto for p in linea)
        texto_linea_lower = texto_linea.lower()
        if any(palabra in texto_linea_lower for palabra in LINEA_NO_PACIENTE):
            continue
        m_nombre = next(
            (
                m
                for m in RE_NOMBRE.finditer(texto_linea)
                if m.group(0).split()[0] not in PALABRAS_NO_NOMBRE
            ),
            None,
        )
        if not m_nombre:
            continue
        nombre = m_nombre.group(0).upper()  # ya viene en mayúscula de la hoja, pero forzamos

        # posición x del fin del nombre (para desempatar teléfonos por cercanía) y las
        # palabras que componen el match (para recortar esa región después): reconstruimos
        # los mismos offsets de caracteres que arma texto_linea (join con un espacio simple).
        x_fin_nombre = linea[0].left if linea else 0
        palabras_nombre: list[_Palabra] = []
        cursor = 0
        for p in linea:
            inicio = cursor
            cursor += len(p.texto) + 1  # +1 por el espacio separador
            if inicio < m_nombre.end() and cursor - 1 > m_nombre.start():
                palabras_nombre.append(p)
                x_fin_nombre = p.right  # borde derecho de la última palabra del nombre, no
                # el izquierdo — si no, la distancia de desempate queda corrida hacia la
                # izquierda por el ancho de esa palabra.

        mejor_telefono = None
        mejor_distancia = None
        palabras_telefono: list[_Palabra] = []
        for offset in range(0, LINEAS_DE_BUSQUEDA_TELEFONO + 1):
            j = i + offset
            if j >= len(lineas):
                break
            if offset > 0:
                texto_linea_j = " ".join(p.texto for p in lineas[j])
                ya_es_otro_paciente = any(
                    m.group(0).split()[0] not in PALABRAS_NO_NOMBRE
                    for m in RE_NOMBRE.finditer(texto_linea_j)
                )
                if ya_es_otro_paciente:
                    # Esta línea ya es la fila de OTRO paciente (tiene su propio nombre) —
                    # cortamos acá para no robarle su teléfono al de más arriba. Sin este
                    # corte, un nombre sin teléfono en su propia línea (por blur/skew) podía
                    # terminar con el teléfono del paciente de 1-2 líneas más abajo, sin
                    # ningún aviso en la revisión (Tesseract lo lee bien, solo que es de otra
                    # persona).
                    break
            for limpio, x_izq, tramo in _candidatos_telefono_en_linea(lineas[j]):
                dist_x = abs(x_izq - x_fin_nombre)
                # Preferimos el candidato más largo ANTES que el más cercano: en estas
                # planillas los teléfonos reales tienen 9-10 dígitos y los números de
                # ficha/documento vecinos casi siempre son más cortos (6-8) — confirmado
                # contra datos reales. Elegir por longitud primero evita agarrar una ficha
                # solo por estar un poco más cerca del nombre que el teléfono real.
                distancia = (offset, -len(limpio), dist_x)
                if mejor_distancia is None or distancia < mejor_distancia:
                    mejor_distancia = distancia
                    mejor_telefono = limpio
                    palabras_telefono = tramo
            if mejor_telefono and offset == 0:
                break  # ya encontró en la misma línea del nombre, no hace falta seguir

        # Segunda pasada de Tesseract, recortada a solo esta región y restringida al alfabeto
        # esperado (letras para el nombre, dígitos para el teléfono). SOLO se intenta cuando
        # la pasada general ya viene dudosa (poca confianza, o un teléfono de largo raro) —
        # probado contra una foto real: refinar un dato que la pasada general ya leyó bien a
        # veces lo empeora (el recorte también puede confundirse), así que no vale la pena
        # arriesgar un dato ya confiable solo por intentar "mejorarlo".
        confianza_nombre = _promedio_confianza(palabras_nombre)
        if confianza_nombre < 0 or confianza_nombre < UMBRAL_CONFIANZA_PARA_REFINAR:
            nombre_refinado = _recortar_y_refinar(img, palabras_nombre, ALFABETO_NOMBRE)
            if RE_NOMBRE.fullmatch(nombre_refinado.strip()):
                nombre = nombre_refinado.strip()

        confianza_telefono = _promedio_confianza(palabras_telefono)
        largo_actual = len(mejor_telefono or "")
        telefono_dudoso = confianza_telefono < 0 or confianza_telefono < UMBRAL_CONFIANZA_PARA_REFINAR
        largo_raro = largo_actual not in (9, 10)  # los teléfonos reales de esta zona miden 9-10
        if palabras_telefono and (telefono_dudoso or largo_raro):
            refinado = _limpiar_telefono(_recortar_y_refinar(img, palabras_telefono, DIGITOS_TELEFONO))
            if 6 <= len(refinado) <= 11 and len(refinado) >= largo_actual:
                mejor_telefono = refinado

        candidatos.append(
            FilaImport(
                nombre=nombre,
                contacto=mejor_telefono or "",
                origen=f"OCR línea {i + 1}",
                confianza_nombre=confianza_nombre,
                confianza_telefono=confianza_telefono,
            )
        )

    return candidatos
