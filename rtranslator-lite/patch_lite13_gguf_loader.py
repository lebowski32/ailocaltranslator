#!/usr/bin/env python3
from pathlib import Path
import sys

ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else "RTranslator")
engine = ROOT / "app/src/main/java/nie/translator/rtranslator/voice_translation/neural_networks/translation/LlamaCppTranslationEngine.java"
build = ROOT / "app/build.gradle"
provider_files = [
    ROOT / "app/src/main/AndroidManifest.xml",
    ROOT / "app/src/main/java/nie/translator/rtranslator/access/UserDataFragment.java",
    ROOT / "app/src/main/java/nie/translator/rtranslator/settings/SettingsFragment.java",
]
for p in [engine, build, *provider_files]:
    if not p.exists():
        raise SystemExit(f"Missing required file: {p}")

# Pre-flight check for libai-chat.so in LlamaCppTranslationEngine
e = engine.read_text(encoding="utf-8")
needle_load = '    public void load() throws Exception {\n        synchronized (lock) {\n            lastLoadError = "";\n'
replacement_load = '''    public void load() throws Exception {
        synchronized (lock) {
            lastLoadError = "";
            try {
                String nativeDir = global.getApplicationInfo().nativeLibraryDir;
                java.io.File nativeLib = new java.io.File(nativeDir, "libai-chat.so");
                if (!nativeLib.exists()) {
                    try {
                        System.loadLibrary("ai-chat");
                        Log.i(TAG, "libai-chat.so loaded directly via System.loadLibrary");
                    } catch (Throwable tLoad) {
                        lastLoadError = "Native library libai-chat.so not found in " + nativeDir
                                + " and System.loadLibrary failed: " + tLoad.getMessage();
                        throw new IllegalStateException(lastLoadError);
                    }
                }
            } catch (IllegalStateException e) {
                throw e;
            } catch (Throwable t) {
                Log.w(TAG, "Could not pre-check native lib directory", t);
            }
'''
if needle_load in e:
    e = e.replace(needle_load, replacement_load, 1)

# Validate the actual GGUF magic before handing a file to native llama.cpp.
needle = '''            if (!modelFile.isFile() || !modelFile.canRead()) {\n                lastLoadError = "GGUF file is not readable";\n                throw new IllegalStateException("Cannot read GGUF: " + modelFile.getAbsolutePath());\n            }\n            Log.i(TAG, "Loading GGUF model: " + modelFile.getAbsolutePath() + " (" + modelFile.length() + " bytes)");\n'''
replacement = '''            if (!modelFile.isFile() || !modelFile.canRead()) {\n                lastLoadError = "GGUF file is not readable";\n                throw new IllegalStateException("Cannot read GGUF: " + modelFile.getAbsolutePath());\n            }\n            if (modelFile.length() < 16) {\n                lastLoadError = "GGUF file is too small (" + modelFile.length() + " bytes)";\n                throw new IllegalStateException(lastLoadError);\n            }\n            try (java.io.FileInputStream in = new java.io.FileInputStream(modelFile)) {\n                byte[] magic = new byte[4];\n                if (in.read(magic) != 4 || magic[0] != 'G' || magic[1] != 'G' || magic[2] != 'U' || magic[3] != 'F') {\n                    lastLoadError = "Invalid GGUF header; file does not start with GGUF magic";\n                    throw new IllegalStateException(lastLoadError);\n                }\n            }\n            Log.i(TAG, "Loading GGUF model: " + modelFile.getAbsolutePath() + " (" + modelFile.length() + " bytes)");\n'''
if needle not in e:
    raise SystemExit("Lite12 readable-file block missing")
e = e.replace(needle, replacement, 1)
engine.write_text(e, encoding="utf-8")

# Pre-flight check for libonnxruntime.so in Translator.java
translator_file = ROOT / "app/src/main/java/nie/translator/rtranslator/voice_translation/neural_networks/translation/Translator.java"
if translator_file.exists():
    te = translator_file.read_text(encoding="utf-8")
    ort_needle = '                try {\n                    Log.i("RTranslatorLite13", "Initializing matched ONNX Runtime 1.27.1");'
    ort_replacement = '''                try {
                    String nativeDir = global.getApplicationInfo().nativeLibraryDir;
                    java.io.File ortLib = new java.io.File(nativeDir, "libonnxruntime.so");
                    if (!ortLib.exists()) {
                        try {
                            System.loadLibrary("onnxruntime");
                            Log.i("RTranslatorLite13", "libonnxruntime.so loaded directly via System.loadLibrary");
                        } catch (Throwable tOrt) {
                            String msg = "ONNX Runtime native library not found in " + nativeDir
                                    + " and System.loadLibrary failed: " + tOrt.getMessage();
                            Log.e("RTranslatorLite13", msg);
                            mainHandler.post(() -> initListener.onFailure(new int[]{ErrorCodes.ERROR_LOADING_MODEL}, 0));
                            return;
                        }
                    }
                    Log.i("RTranslatorLite13", "Initializing matched ONNX Runtime 1.27.1");'''
    if ort_needle in te:
        te = te.replace(ort_needle, ort_replacement, 1)
        translator_file.write_text(te, encoding="utf-8")

manifest_file = ROOT / "app/src/main/AndroidManifest.xml"
if manifest_file.exists():
    m = manifest_file.read_text(encoding="utf-8")
    if 'android:extractNativeLibs=' not in m:
        m = m.replace('<application\n', '<application\n        android:extractNativeLibs="true"\n', 1)
        manifest_file.write_text(m, encoding="utf-8")



# Separate Lite13 package so Lite12 remains installable for comparison.
b = build.read_text(encoding="utf-8")
if 'applicationId "nie.translator.rtranslator.lite12"' not in b:
    raise SystemExit("Lite12 applicationId missing")
b = b.replace('applicationId "nie.translator.rtranslator.lite12"', 'applicationId "nie.translator.rtranslator.lite13"', 1)
b = b.replace('versionCode 30014', 'versionCode 30015', 1)
b = b.replace("versionName '3.0.0-alpha3-lite12'", "versionName '3.0.0-alpha3-lite13'", 1)
build.write_text(b, encoding="utf-8")

changed_labels = 0
for strings_xml in (ROOT / "app/src/main/res").glob("values*/strings.xml"):
    s = strings_xml.read_text(encoding="utf-8")
    if "RTranslator Lite12" in s:
        strings_xml.write_text(s.replace("RTranslator Lite12", "RTranslator Lite13"), encoding="utf-8")
        changed_labels += 1
if changed_labels == 0:
    raise SystemExit("Lite12 app label missing")

for p in provider_files:
    s = p.read_text(encoding="utf-8")
    if "com.gallery.RTranslator.lite12.provider" not in s:
        raise SystemExit(f"Lite12 provider missing in {p}")
    p.write_text(s.replace("com.gallery.RTranslator.lite12.provider", "com.gallery.RTranslator.lite13.provider"), encoding="utf-8")

for p in (ROOT / "app/src/main/java").rglob("*.java"):
    s = p.read_text(encoding="utf-8")
    if "RTranslatorLite12" in s:
        p.write_text(s.replace("RTranslatorLite12", "RTranslatorLite13"), encoding="utf-8")

print("Lite13 GGUF loader patch complete:")
print(" - validates GGUF magic before JNI")
print(" - retains Lite11 OCR/Documents and Lite12 runtime fixes")
print(" - applicationId nie.translator.rtranslator.lite13")
