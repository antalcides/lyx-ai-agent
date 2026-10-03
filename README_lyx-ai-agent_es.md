# Agente de IA de LyX 🤖

Asistente con inteligencia artificial para la edición de documentos **LyX** y **LaTeX**.
Admite **7 proveedores de IA** (en la nube y locales) con una interfaz gráfica de usuario de tema oscuro.

---

## Características

| Característica                | Descripción                                                                                  |
| ----------------------------- | -------------------------------------------------------------------------------------------- |
| 📝 **Crear**                  | Generar documentos LaTeX completos a partir de lenguaje natural                              |
| ✏️ **Editar**                 | Abre un archivo existente y aplícale los cambios, manteniendo todo lo demás intacto          |
| 📑 **Plantilla**              | Crea un nuevo documento a partir de uno existente; el original nunca se modifica             |
| 🔧 **Correcto**               | Soluciona errores de sintaxis, problemas de compilación y errores de LaTeX                   |
| 🌐 **Traducir**               | Traduce documentos conservando todo el marcado LaTeX                                         |
| 💾 **Guardado seguro**        | Con marca de tiempo `.bak` Copia de seguridad + escritura atómica antes de sobrescribir nada |
| 🔄 **Transmisión en directo** | Vea la respuesta de la IA aparecer token por token                                           |
| 🧪 **Prueba**                 | Comprobación de conectividad con un solo clic por proveedor                                  |
| 🎨 **Resaltado de sintaxis**  | Resaltado de sintaxis básico de LaTeX en el área de salida                                   |

---

## Trabajar con documentos

La barra que se encuentra debajo de los botones de modo es donde se realiza toda la gestión de archivos.

### Modificar un archivo en su lugar

1. Haz clic en **📂 Abrir** y elige una `.tex` / `.lyx` archivo.
   El documento se carga en el cuadro grande y el modo cambia a **✏️ Editar documento**.
2. Escriba lo que desea cambiar en el campo **Instrucción**, por ejemplo:
   *“Añadir una sección de Resultados y traducir el resumen al inglés”*.
3. Haz clic en **▶ Enviar a la IA**.
4. Revisa el resultado. Puedes editar el cuadro de respuesta directamente antes de guardar.
5. Haz clic en **💾 Guardar**.

Antes de sobrescribir, la aplicación solicita confirmación y crea una copia de seguridad llamada
`informe.20260916-164230.tex.bak` junto al archivo, y solo entonces escribe el nuevo
contenido atómicamente. Si el archivo fue modificado por otro programa mientras tanto,
Recibes una segunda advertencia.

### Utilice un archivo como plantilla

1. Haz clic en **📑 Usar como plantilla** y selecciona el documento de origen.
2. Elija dónde se debe guardar el **nuevo** documento (un nombre como
   `informe-nuevo.tex` se sugiere).
3. La plantilla se carga en el cuadro y la nueva ruta se convierte en el destino de guardado.
4. Describe qué construir, luego **▶ Enviar a la IA** y **💾 Guardar**.

El archivo de plantilla en sí nunca se modifica; solo se modifica el archivo nuevo.

### Lo que se escribe en el disco

Solo se guarda el bloque de código. Si la IA responde con una explicación seguida de
un ```bloque de látex, la prosa se descarta y solo se escribe el documento. Esto
es lo que hace que “editar en el mismo lugar” sea seguro: nunca terminan las vallas de Markdown ni los comentarios.
dentro de tu `.tex` archivo.

---

## Proveedores de IA compatibles

| Proveedor         | Tipo     | Notas                                                         |
| ----------------- | -------- | ------------------------------------------------------------- |
| **OpenAI**        | ☁️ Nube  | Requiere una cuenta válida `sk-…` clave                       |
| **Antrópico**     | ☁️ Nube  | Requiere crédito en la cuenta                                 |
| **Google Gemini** | ☁️ Nube  | La lista de modelos se obtiene en tiempo real                 |
| **OpenRouter**    | ☁️ Nube  | Más de 400 modelos; `:free` Las modelos no necesitan créditos |
| **OmniRoute**     | 💻 Local | Puerta de enlace en `http://localhost:20128/v1` por defecto   |
| **Ollama**        | 💻 Local | `http://localhost:11434`                                      |
| **LM Studio**     | 💻 Local | `http://localhost:1234/v1`                                    |

---

## Instalación

### Windows 11

```powershell
# Option A — PowerShell (recommended)
powershell -ExecutionPolicy Bypass -File install_windows.ps1

# Option B — run manually
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
```

A continuación, haga doble clic en **LyX AI Agent** en su escritorio o ejecute:

```cmd
LyxAI.bat
```

### Linux (Debian 12 / 13)

```bash
chmod +x install_linux.sh
./install_linux.sh
```

Luego corre `lyx-ai-agent`o encuéntralo en el menú de tu aplicación en
**Oficina / Ciencias**.

---

## Inicio rápido

1. **Seleccione un proveedor** en el menú desplegable.
2. **Introduzca la clave API** a través de `🔑 API Key` (No es necesario para Ollama / LM Studio).
3. Haz clic en **🧪 Probar** para confirmar que el proveedor realmente responde.
4. **Elige un modo**: Crear · Editar · Corregir · Traducir.
5. Escriba su solicitud o abra un documento.
6. Haz clic en **▶ Enviar a la IA**, revisa y luego **💾 Guardar**.

---

## Diagnóstico

Compruebe todos los proveedores configurados sin abrir la interfaz gráfica de usuario:

```bash
.venv/Scripts/python.exe main.py --diagnose
```

Imprime una línea por proveedor con el modelo que probó y el resultado:

```
provider           model                                result
------------------------------------------------------------------------------------------------
OpenAI             gpt-4o                               FAIL  Error code: 401 - Incorrect API key
Google Gemini      gemini-3.5-flash                     OK    OK
Ollama (Local)     qwen2.5-coder:3b                     OK    OK
OpenRouter         nex-agi/nex-n2.5-pro:free            OK    OK
OmniRoute          auto/best-coding                     OK    OKping
```

Ejecutar el conjunto de pruebas:

```bash
.venv/Scripts/python.exe tests/test_document_ops.py
```

---

## Solución de problemas

Síntoma | Causa | Solución |
| ----------------------------------- | ------------------------------------------------------------------ | --------------------------------------------------------------------------------------------------- |
| `401 Incorrect API key`             | La clave es incorrecta o está mal formada | Pégala de nuevo con **🔑 Clave API**. Un error `api-key:` o `Bearer` El prefijo se elimina automáticamente |
| `401 Missing Authentication header` | Clave almacenada con un prefijo | Se corrige automáticamente al cargar — ver `sanitize_api_key`                                                |
| `400 credit balance is too low`     | La cuenta no tiene saldo | Recarga o cambia a un proveedor local |
| `404 model no longer available`     | El modelo ha sido retirado | Haga clic en **↻** para actualizar la lista y seleccionar un modelo actual |
| `502` / `ProxyError` en OmniRoute | URL base incorrecta | Configúrela en `http://localhost:20128/v1` con **🌐 URL** |
| `Connection error` En LM Studio | El servidor local no está en funcionamiento | Inicie LM Studio y habilite su servidor |
| `429 quota exceeded`                | Se ha agotado la cuota del plan gratuito | Espere o utilice otro proveedor |
| La lista de proveedores muestra modelos extraños | No se pudo obtener la lista en vivo, se muestra la alternativa integrada | La barra de estado se vuelve ámbar y sugiere **🧪 Prueba** |

---

## Configuración

Configuración en vivo en `config.json` (junto a `main.py`) y también se puede editar mediante
**⚙ Ajustes**.

### Claves API

| Proveedor                | Variable de entorno (alternativa) |
| ------------------------ | --------------------------------- |
| OpenAI                   | `OPENAI_API_KEY`                  |
| Antrópico                | `ANTHROPIC_API_KEY`               |
| Géminis `GOOGLE_API_KEY` |                                   |
| OpenRouter               | `OPENROUTER_API_KEY`              |
| OmniRoute                | configurado en Ajustes → URL base |

### Proveedores locales

- **Ollama**: comienza con `ollama serve` - por defecto `http://localhost:11434`
- **LM Studio**: iniciar el servidor local — predeterminado `http://localhost:1234/v1`
- **OmniRoute**: iniciar la puerta de enlace — por defecto `http://localhost:20128/v1`

> ⚠️ **`config.json` Almacena sus claves API en texto plano.** Está listado en
> `.gitignore` — manténlo así y nunca lo cometas.

### Configuración del documento

En **⚙ Ajustes → 📄 Documentos**:

- **Crear una marca de tiempo `.bak` Copiar antes de sobrescribir un archivo** (predeterminado: activado)
- **Solicitar confirmación antes de sobrescribir un archivo existente** (predeterminado: activado)

---

## Estructura del proyecto

```
lyx-ai-agent/
├── main.py                  # Entry point (+ --diagnose)
├── app/
│   ├── gui.py               # Main Tkinter GUI
│   ├── config.py            # Settings + API key sanitising
│   ├── utils.py             # Prompts, document extraction, safe file I/O
│   └── providers/           # One file per AI provider
│       ├── base.py          # AIProvider ABC + model preference
│       ├── openai_provider.py
│       ├── anthropic_provider.py
│       ├── gemini_provider.py
│       ├── ollama_provider.py
│       ├── lmstudio_provider.py
│       ├── openrouter_provider.py
│       └── omniroute_provider.py
├── tests/
│   └── test_document_ops.py # Tests for extraction, keys and file safety
├── assets/
│   ├── logo-lyx-ai.png
│   └── logo-lyx-ai.ico
├── config.json              # User settings + keys (gitignored)
├── requirements.txt
├── install_windows.ps1      # Windows installer
├── LyxAI.bat                # Windows launcher
└── install_linux.sh         # Linux installer
```

---

## Requisitos

- Python **3.10+**
- `tkinter` (incluido en la mayoría de las instalaciones de Python; en Linux: `sudo apt install python3-tk`)
- Conexión a Internet para proveedores de servicios en la nube.

---

## Licencia

MIT — úselo libremente, modifíquelo según sea necesario.
