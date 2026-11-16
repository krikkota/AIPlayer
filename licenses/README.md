# Third-party materials

The application uses dynamically linked Qt/PySide6/Shiboken, ONNX Runtime, ONNX ASR, NumPy, SoundFile/libsndfile, cffi, imageio-ffmpeg and CPython. Dependency notices copied from installed distributions are in `dependencies/`; versions and copied paths are recorded in `inventory.json`.

Qt/PySide6/Shiboken use the applicable Qt open-source license options. Original LGPL 3 and GPL 3 texts are included. Upstream source and notices: https://code.qt.io/cgit/pyside/pyside-setup.git/ and https://code.qt.io/cgit/qt/qtbase.git/. Qt libraries remain separate native libraries in the application bundle. No changes were made to those libraries.

The export executable supplied by imageio-ffmpeg is a separate process. Its complete reported version, configuration and license are in `FFmpeg-build.txt`. This build enables GPL and libx264; it is not described as LGPL-only. GPL 2 and LGPL 2.1 texts are included. Upstream source/build materials: https://github.com/imageio/imageio-ffmpeg, https://github.com/imageio/imageio-binaries and https://ffmpeg.org/download.html. Qt Multimedia has its own separately bundled FFmpeg libraries and notices.

The GigaAM model is downloaded or connected separately, not shipped with this application. Its MIT notice is included in `GigaAM-MIT.txt`. The ONNX export is pinned in `player/models.py`.

Onest fonts: `Onest-OFL.txt`. Lucide icons: `Lucide-ISC.txt`. Official Ollama logo, reused from the user's Voxsyl reference: `Ollama-MIT.txt`. These notices accompany the corresponding resources.

These files document the private development build and its actual dependencies. A public release also needs a complete corresponding-source/distribution process for its exact bundled native binaries.
