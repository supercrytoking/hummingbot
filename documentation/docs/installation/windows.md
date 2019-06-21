# Windows Source Installation

The Hummingbot code base is designed and optimized for UNIX-based systems such as macOS and Linux. We recommend that Windows users either:

* Install the [Docker version](/installation/docker_windows). Note that it is recommended to use the Docker Toolbox over native Docker in most cases.
* Install in [the cloud](/installation/cloud) by using a native Linux virtual machine.

Hummingbot can also be installed by utilizing the built-in Windows Subsystem for Linux. However, this is only recommended for users familiar with development.

## Installing Hummingbot on Windows Subsystems for Linux

!!! Warning
    Windows source installation has minimal support and is not recommended. We suggest users either install via Docker or use a cloud VM.

Below, we summarize instructions for installing Hummingbot from source on Windows 10, using Windows Subsystem for Linux (WSL). Users may use <a href="ttps://www.virtualbox.org/" target="_blank">VirtualBox</a> rather than WSL.

### 1. Install Ubuntu in Windows Subsystem for Linux

Follow these <a href="https://docs.microsoft.com/en-us/windows/wsl/install-win10" target="_blank">instructions</a> for installing Windows Subsystem for Linux, and then Ubuntu.

### 2. Get the `build-essential` package

![Bash for Windows](/assets/img/bash-for-windows.png)

Start the Bash app and install the `build-essential` package which contains `gcc` and `make`, utility libraries used by Hummingbot's installation script:
```
sudo apt-get update
sudo apt-get install build-essential
```

### 3. Download and run the Anaconda for Linux installer

To manage Python and Python library dependencies, Hummingbot uses Anaconda, an open source environment and package manager that is the current industry standard for data scientists and data engineers.

From Bash, download the Anaconda for Linux installer:
```
wget https://repo.anaconda.com/archive/Anaconda3-2019.03-Linux-x86_64.sh
```

Run the installer:
```
./Anaconda3-2019.03-Linux-x86_64.sh
```

### 4. Install and compile Hummingbot

Afterwards, installation should be identical to installing from source on macOS or Linux.

Follow the [macOS/Linux guide](/installation/macOS_linux) starting on step 2.
