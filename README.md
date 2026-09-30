# OpenTTD-Html5

An unofficial HTML5/WebAssembly port of OpenTTD.

### Controls & Features
* **CTRL + SHIFT + S:** Opens the custom save downloader/uploader (since standard OpenTTD doesn't natively support this on the web)
* Everything else works just like the standard game. Find it at [OpenTTD.org](https://www.openttd.org)

### Compile instructions
***This assumes you are on a Debian based operating system such as Debian 13, Ubuntu, or anything else based on a modern-ish debian kernel.***

This should work for newer versions unless a major revision happens in which i will update *this* file as soon as i notice.

---

### Step 1: Setup
### Install Dependencies
*You can skip this step if you already have Git, CMake, and Python installed.*

First, update your package lists:
```bash
sudo apt-get update
```

Next, Install core build tools and dependencies:
```bash
sudo apt-get install -y git cmake build-essential python3 python3-pip wget curl xz-utils libxml2-dev zlib1g-dev
```
### Clone and install Emscripten
First, clone Emscripten
```bash
cd ~
git clone https://github.com/emscripten-core/emsdk.git ~/emsdk
```
Next, install & activate Emscripten
```bash
cd ~/emsdk
./emsdk install latest
./emsdk activate latest
source ~/emsdk/emsdk_env.sh
```
---
### Step 2: Cloning & configuring OpenTTD's GitHub
### Cloning Openttd
First, clone the GitHub
```bash
cd ~
git clone https://github.com/OpenTTD/OpenTTD.git openttd
```
Second, Switch to the version you are using (15.3 here)
```bash
cd ~/openttd
git checkout -- .
git fetch --tags
git checkout 15.3
```
### Configuring OpenTTD
First, inject liblzma
```bash
EMSDK_PORT_DIR=$(dirname $(readlink -f $(which emcc)))/tools/ports/contrib
mkdir -p "$EMSDK_PORT_DIR"
cp os/emscripten/ports/liblzma.py "$EMSDK_PORT_DIR/"
```
---
### Step 3: Compilation of OpenTTD
### Remove old build files
First, remove old build files for strgen settingsgen and OpenTTD
```bash
rm -rf build-host build-wasm
```
### Compilation
First, Compile strgen and settingsgen
```bash
mkdir build-host && cd build-host
cmake .. && make -j$(nproc) strgen settingsgen && cd ..
```
Second, compile OpenTTD
```bash
emcmake cmake .. -DHOST_BINARY_DIR=../build-host -DCMAKE_BUILD_TYPE=Release -DOPTION_USE_ASSERTS=OFF
emmake make -j$(nproc)
cd ~
```
---
### Step 4: Bundling
First, download [`Bundle.py`](bundle.py)
Second, run Bundle.py 
```bash
python3 bundle.py
```
The compiled file should be in ~/build-wasm
