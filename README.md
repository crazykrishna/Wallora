<div align="center">

# 🌌 Wallora

### Your Desktop, Your Atmosphere.

**Bring your desktop to life with video wallpapers and background music — with simple controls and automatic startup.**

[![Platform](https://img.shields.io/badge/Platform-Windows%2010%20%7C%2011-blue?logo=windows)](#-requirements)
[![Language](https://img.shields.io/badge/Language-Python-yellow?logo=python)](https://www.python.org/)
[![Project](https://img.shields.io/badge/Project-Wallora-8A2BE2)](#-features)

</div>

---

## ✨ What is Wallora?

**Wallora** is a lightweight live wallpaper application for Windows that lets you personalize your desktop with videos stored on your PC. You can also play your favourite music from anywhere in your local storage, set Wallora to launch when you sign in, and stop playback whenever you want.

The idea is simple: **a more personal desktop, without an unnecessarily complicated setup.**

## 🚀 Features

- 🎬 **Local video wallpapers** — choose a video from your PC.
- 🎵 **Background music** — play audio files stored anywhere in your local storage, with looping support.
- ⚡ **Lightweight by design** — focused on a simple, streamlined experience.
- 🔁 **Launch on sign-in** — setup adds Wallora to the Windows Startup folder so it can launch when you log in.
- ⏹️ **Control when it runs** — stop the wallpaper whenever you want.
- 🎞️ **Multiple video formats** — support depends on the playback backend and codecs available on your system.

> **Note:** Playback smoothness and supported formats can vary with your hardware, video encoding, and installed codecs.

## 🖥️ Requirements

Before installing, make sure you have:

- **Windows 10 or Windows 11** — Wallora is designed for Windows only.
- **Python installed** on your PC.
- An internet connection during initial setup so the required Python libraries can be downloaded.

## 📦 Get Wallora

Choose either method to get the project onto your PC:

### Option 1 — Download the ZIP

1. Open the project's GitHub repository.
2. Click **Code → Download ZIP**.
3. Extract the ZIP file to a folder on your PC.
4. Open the extracted **Wallora** project folder.

### Option 2 — Clone the repository

If you have Git installed, open Command Prompt or PowerShell and run:

```bash
git clone YOUR_GITHUB_REPOSITORY_URL
```

Then open the downloaded project folder.

> Replace `YOUR_GITHUB_REPOSITORY_URL` with the actual URL of this repository.

## ⚙️ Install & Run

Wallora includes a convenient setup script, **`setup_and_run.bat`**, to handle the initial setup.

1. Make sure Python is installed.
2. Open the Wallora project folder.
3. Double-click **`setup_and_run.bat`**.
4. Allow the script to download and install the project's required Python libraries.
5. Once setup finishes, the script automatically launches **`wallora.py`**.

**That's it — you're ready to personalize your desktop!** 🎉

### What does the setup script do?

- Downloads the main Python libraries required by Wallora.
- Starts the application by running `wallora.py`.
- Adds Wallora to your Windows Startup folder so it can launch automatically after you sign in.

The setup script needs internet access for dependency installation. Windows may display a security prompt; only run the script if you trust the source and have reviewed its contents.

## 🎧 Make it yours

1. Launch Wallora.
2. Select a video from your local storage for your wallpaper.
3. Choose your favourite audio file from anywhere on your PC.
4. Enable or use startup launching to have Wallora open when you sign in.
5. Stop playback whenever you want a break from the live wallpaper.

Enjoy your own combination of motion and music. 🌠

## 🛠️ Troubleshooting

- **Python not found:** Install Python and make sure it is available from the command line. If the installer offers an option to add Python to `PATH`, enable it.
- **Setup cannot download libraries:** Check your internet connection and try running `setup_and_run.bat` again.
- **A video or audio file will not play:** Try another file. Playback depends on the media backend and supported codecs.
- **Wallora does not start at sign-in:** Check that the startup shortcut is present in your Windows Startup folder and that startup apps are allowed.
- **Playback is not smooth:** Try a lower-resolution or less heavily encoded video; performance varies by device and file.

## 🤝 Feedback & Contributions

Have an idea, found an issue, or want to improve Wallora? Feel free to open an issue or submit a pull request through the GitHub repository.

If you try Wallora, feedback on setup, playback, resource usage, and usability is especially welcome.

## 📄 License

Check the repository for license information before redistributing or modifying Wallora.

---

<div align="center">

**Wallora — Your Desktop, Your Atmosphere.** 🌌

Made for a desktop that feels a little more like yours.

</div>
