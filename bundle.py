import base64, os, re, urllib.request, tarfile, zipfile

os.chdir(os.path.expanduser("~/openttd/build-wasm"))

required_files = ["openttd.html", "openttd.js", "openttd.wasm", "openttd.data"]
for f in required_files:
    if not os.path.exists(f):
        print(f"ERROR: Could not find {f} in build-wasm!")
        exit(1)

os.makedirs("temp_assets", exist_ok=True)

def download_file(url, output_path):
    if os.path.exists(output_path):
        return
    print(f"Downloading {url}...")
    req = urllib.request.Request(
        url, 
        headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    )
    with urllib.request.urlopen(req) as response, open(output_path, 'wb') as out_file:
        out_file.write(response.read())

# 1. Download OpenGFX (Graphics)
opengfx_url = "https://cdn.openttd.org/opengfx-releases/7.1/opengfx-7.1-all.zip"
opengfx_zip = "temp_assets/opengfx.zip"
download_file(opengfx_url, opengfx_zip)

with zipfile.ZipFile(opengfx_zip, 'r') as z:
    z.extractall("temp_assets/opengfx")
    for inner in os.listdir("temp_assets/opengfx"):
        if inner.endswith(".tar"):
            with tarfile.open(os.path.join("temp_assets/opengfx", inner), "r") as tar:
                tar.extractall("temp_assets/extracted_gfx")

# 2. Download OpenSFX (Sound)
opensfx_url = "https://cdn.openttd.org/opensfx-releases/1.0.3/opensfx-1.0.3-all.zip"
opensfx_zip = "temp_assets/opensfx.zip"
download_file(opensfx_url, opensfx_zip)

with zipfile.ZipFile(opensfx_zip, 'r') as z:
    z.extractall("temp_assets/opensfx")
    for inner in os.listdir("temp_assets/opensfx"):
        if inner.endswith(".tar"):
            with tarfile.open(os.path.join("temp_assets/opensfx", inner), "r") as tar:
                tar.extractall("temp_assets/extracted_sfx")

print("1/4 Encoding openttd.data to Base64...")
with open("openttd.data", "rb") as f:
    data_b64 = base64.b64encode(f.read()).decode("utf-8")

print("2/4 Encoding openttd.wasm to Base64...")
with open("openttd.wasm", "rb") as f:
    wasm_b64 = base64.b64encode(f.read()).decode("utf-8")

asset_files_js = ""

gfx_dir = "temp_assets/extracted_gfx"
if os.path.exists(gfx_dir):
    for root, dirs, files in os.walk(gfx_dir):
        for file in files:
            filepath = os.path.join(root, file)
            with open(filepath, "rb") as bf:
                b64_content = base64.b64encode(bf.read()).decode("utf-8")
                asset_files_js += f'FS.createDataFile("/baseset/opengfx", "{file}", _base64ToUint8Array("{b64_content}"), true, true, true);\n'

sfx_dir = "temp_assets/extracted_sfx"
if os.path.exists(sfx_dir):
    for root, dirs, files in os.walk(sfx_dir):
        for file in files:
            filepath = os.path.join(root, file)
            with open(filepath, "rb") as bf:
                b64_content = base64.b64encode(bf.read()).decode("utf-8")
                asset_files_js += f'FS.createDataFile("/baseset/opensfx", "{file}", _base64ToUint8Array("{b64_content}"), true, true, true);\n'

print("3/4 Reading openttd.js and openttd.html...")
with open("openttd.js", "r", encoding="utf-8", errors="ignore") as f:
    js_content = f.read()

with open("openttd.html", "r", encoding="utf-8", errors="ignore") as f:
    html = f.read()

print("4/4 Patching engine bugs and injecting standalone bundle...")
js_content = js_content.replace('</script>', '<\\/script>')

for view in ['HEAPU8', 'HEAP8', 'HEAPU16', 'HEAP16', 'HEAPU32', 'HEAP32']:
    js_content = js_content.replace(f'Module.{view}.', f'(Module.{view} || {view}).')

html = html.replace('<script async type="text/javascript" src="openttd.js"></script>', '')
html = re.sub(r'<script[^>]*src=[\'"]?openttd\.js[\'"]?[^>]*>.*?</script>', '', html, flags=re.IGNORECASE | re.DOTALL)

magic_injection = f"""
<script>
  function _base64ToUint8Array(base64) {{
    var binary_string = window.atob(base64);
    var len = binary_string.length;
    var bytes = new Uint8Array(len);
    for (var i = 0; i < len; i++) {{
      bytes[i] = binary_string.charCodeAt(i);
    }}
    return bytes;
  }}

  function _base64ToArrayBuffer(base64) {{
    var binary_string = window.atob(base64);
    var len = binary_string.length;
    var bytes = new Uint8Array(len);
    for (var i = 0; i < len; i++) {{
      bytes[i] = binary_string.charCodeAt(i);
    }}
    return bytes.buffer;
  }}

  const originalFetch = window.fetch;
  window.fetch = async function(url, options) {{
    if (typeof url === 'string') {{
      if (url.endsWith('openttd.wasm')) {{
        return new Response(_base64ToArrayBuffer("{wasm_b64}"), {{ headers: {{ 'Content-Type': 'application/wasm' }} }});
      }}
      if (url.endsWith('openttd.data')) {{
        return new Response(_base64ToArrayBuffer("{data_b64}"), {{ headers: {{ 'Content-Type': 'application/octet-stream' }} }});
      }}
    }}
    return originalFetch(url, options);
  }};

  var Module = window.Module || {{}};
  Module.arguments = Module.arguments || [];
  Module.onAbort = Module.onAbort || function(what) {{ console.error('Aborted:', what); }};
  Module.preRun = Module.preRun || [];
  Module.preRun.push(function() {{
    try {{ FS.mkdir('/baseset'); }} catch(e) {{}}
    try {{ FS.mkdir('/baseset/opengfx'); }} catch(e) {{}}
    try {{ FS.mkdir('/baseset/opensfx'); }} catch(e) {{}}
    {asset_files_js}
  }});
  window.Module = Module;
</script>
<script>
  {js_content}
</script>
"""

if '</body>' in html:
    html = html.replace('</body>', magic_injection + '\n</body>')
else:
    html += magic_injection

picker_code = """
<div id="save-ui" style="display: none; position: absolute; top: 10px; right: 10px; z-index: 9999; background: rgba(0,0,0,0.9); padding: 10px 14px; border-radius: 6px; color: white; font-family: sans-serif; font-size: 12px; flex-direction: column; gap: 8px; box-shadow: 0 4px 10px rgba(0,0,0,0.5);">
  <div style="font-weight: bold; border-bottom: 1px solid #555; padding-bottom: 4px; display: flex; justify-content: space-between; align-items: center;">
    <span>💾 Save Manager</span>
    <span style="font-size: 10px; color: #aaa;">(Ctrl+Shift+S)</span>
  </div>
  <div style="display: flex; gap: 8px; margin-top: 4px;">
    <button id="downloadSavesBtn" style="cursor: pointer; padding: 6px 12px; background: #28a745; color: white; border: none; border-radius: 4px; font-weight: bold;">💾 Download Saves</button>
    <label style="cursor: pointer; padding: 6px 12px; background: #007acc; color: white; border-radius: 4px; font-weight: bold;">
      📂 Load Save File
      <input type="file" id="uploadSaveInput" accept=".sav" style="display: none;">
    </label>
  </div>
</div>

<script>
  const POSSIBLE_PATHS = [
    '/home/web_user/.openttd/save',
    '/home/web_user/.local/share/openttd/save',
    '/saves'
  ];

  window.addEventListener('keydown', function(e) {
    if (e.ctrlKey && e.shiftKey && (e.key === 'S' || e.key === 's')) {
      e.preventDefault();
      const ui = document.getElementById('save-ui');
      ui.style.display = ui.style.display === 'none' ? 'flex' : 'none';
    }
  });

  document.getElementById('downloadSavesBtn').addEventListener('click', function() {
    if (typeof FS === 'undefined') return alert('Game engine not loaded yet!');
    let downloadedCount = 0;
    POSSIBLE_PATHS.forEach(savePath => {
      if (FS.analyzePath(savePath).exists) {
        const files = FS.readdir(savePath);
        for (const file of files) {
          if (file.endsWith('.sav')) {
            const content = FS.readFile(savePath + '/' + file);
            const blob = new Blob([content], { type: 'application/octet-stream' });
            const a = document.createElement('a');
            a.href = URL.createObjectURL(blob);
            a.download = file;
            a.click();
            URL.revokeObjectURL(a.href);
            downloadedCount++;
          }
        }
      }
    });
    if (downloadedCount === 0) {
      alert('No save files found! Make sure to hit "Save Game" inside OpenTTD first.');
    }
  });

  document.getElementById('uploadSaveInput').addEventListener('change', function(e) {
    const file = e.target.files[0];
    if (!file || typeof FS === 'undefined') return;
    const reader = new FileReader();
    reader.onload = function(evt) {
      const data = new Uint8Array(evt.target.result);
      POSSIBLE_PATHS.forEach(savePath => {
        const parts = savePath.split('/').filter(Boolean);
        let curr = '';
        parts.forEach(part => {
          curr += '/' + part;
          try { FS.mkdir(curr); } catch(err) {}
        });
        try { FS.writeFile(savePath + '/' + file.name, data); } catch(err) {}
      });
      alert('Loaded "' + file.name + '" into game! Go to in-game "Load Game" menu to play.');
    };
    reader.readAsArrayBuffer(file);
  });
</script>
"""

html = html.replace("<body>", "<body>\n" + picker_code)
output_file = "openttd_standalone.html"

print("5/5 Writing openttd_standalone.html...")
with open(output_file, "w", encoding="utf-8") as f:
    f.write(html)

size = round(os.path.getsize(output_file) / (1024 * 1024), 2)
print(f"SUCCESS! Created local {output_file} ({size} MB)")
