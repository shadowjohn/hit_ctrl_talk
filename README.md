# hit_ctrl_talk

這是一個 Windows `x64` 語音輸入工具。

單獨按住任一顆 `Ctrl` 一小段時間後開始錄音，放開全部 `Ctrl` 後停止錄音，接著使用 `faster-whisper` 做語音辨識，再透過 `OpenCC` 把簡體中文轉成正體中文，最後把文字送進目前游標所在的應用程式。

# 作者

羽山秋人 (https://3wa.tw)

# 版本

V0.0.1

## 功能行為

- 一般快捷鍵如 `Ctrl+C`、`Ctrl+V`、`Ctrl+X`、`Ctrl+Z`、`Ctrl+S` 應可正常使用。
- 只有在單獨按住 `Ctrl` 超過 `300ms` 時才會開始錄音。
- 如果 `Ctrl` 還在候選狀態時又按了其他鍵，會立刻取消語音模式。
- 如果已經開始錄音後又按了其他鍵，這次錄音會直接丟棄。
- 啟動後會在右下角系統匣顯示 `icon.png` 圖示，右鍵可看到 `About` / `Quit`，左鍵會觸發 `About`。
- 預設輸出模式為剪貼簿貼上，也支援直接送出 Unicode 文字。
- 在 `--device auto` 模式下，Whisper 會先嘗試使用 `CUDA`，失敗時自動回退到 `CPU`。

## 建議 Python 版本

建議使用 Python `3.11` 或 `3.12` 進行開發與打包。`faster-whisper` 在 Python `3.13` 上可能會因環境不同而有相容性差異。

## Conda 環境建立

```powershell
mkdir d:\tools
cd d:\tools
git clone https://github.com/shadowjohn/hit_ctrl_talk
cd D:\mytools\hit_ctrl_talk
conda create -p hit-ctrl-talk python=3.11 -y
conda activate D:\mytools\hit_ctrl_talk\hit-ctrl-talk

pip install -r requirements.txt
```

## 執行方式

```powershell
python hit_ctrl_talk.py
```

常用參數範例：

```powershell
python hit_ctrl_talk.py --model small --paste-mode clipboard --device auto --hold-ms 300
python hit_ctrl_talk.py --paste-mode unicode
python hit_ctrl_talk.py --device cpu
python hit_ctrl_talk.py --device-index 1

# 啥都不寫就自動 --model small --paste-mode clipboard --device auto --hold-ms 300
python hit_ctrl_talk.py 
```

## GPU 說明

- `--device auto`：先嘗試 `CUDA`，失敗後回退 `CPU`
- `--device cuda`：強制使用 GPU
- `--device cpu`：只使用 CPU
- 目標機器即使沒有 GPU，也仍可透過 CPU 模式執行
- Nvidia 1080 至少可以作到放開 Ctrl 後 1 秒內馬上出字 (10秒鐘的錄音時長)

## Windows 打包方式

建議在乾淨的 conda 環境中進行打包：

```powershell
pyinstaller --noconfirm --clean --onefile --console hit_ctrl_talk.py
或是執行
build.bat

```

輸出的結果位於 `dist\hit_ctrl_talk.exe`，理論上可在一般 Windows `x64` 主機上直接執行，不需要另外安裝 Python 或 conda。


## 模型下載

`faster-whisper` 會在第一次使用時下載所選模型。為了避免打包檔過大，預設不會把模型直接包進執行檔中。

## 疑難排解

- 如果麥克風錄音失敗，請先確認 Windows 麥克風權限與錄音裝置設定是否正確。
- 如果 `CUDA` 無法載入，程式在 `--device auto` 模式下應會自動回退到 CPU。
- 如果某個程式不接受剪貼簿貼上，可改用 `--paste-mode unicode`。
- 若目標應用程式輸入異常，建議先用記事本測試，確認是全域輸入問題還是特定軟體相容性問題。
- 如果發生 cublas64_12.dll 找不到，語音辨識很慢的話，
請參考：https://github.com/m-bain/whisperX/issues/1087
然後至：https://github.com/Purfview/whisper-standalone-win/releases/tag/libs
下載：cuBLAS.and.cuDNN_CUDA12_win_v3.7z

如果是 conda 環境，把 cuBLAS.and.cuDNN_CUDA12_win_v3.7z 解壓縮，把裡面的 dll 與 
D:\mytools\hit_ctrl_talk\hit-ctrl-talk\python.exe 放在同個目錄即可

如果是編成 dist\hit-ctrl-talk.exe 就解壓縮，把裡面的 dll 與 這個 hit-ctrl-talk.exe 放一起即可

