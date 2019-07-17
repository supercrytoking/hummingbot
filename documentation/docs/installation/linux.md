# Linux Installation Using Docker

You can install Docker and/or Hummingbot by selecting ***either*** of the following options from the tabs below:

1. **Easy Install**: download and use automated install scripts.
2. **Manual Installation**: run install commands manually.

## Existing Docker Installation

If you already have Docker installed, use the following commands to install and start Hummingbot:

#### Install tmux

```bash tab="Ubuntu / Debian"
sudo apt-get update
sudo apt-get install -y tmux
```

```bash tab="CentOS"
sudo yum -y install tmux
```


#### Run Hummingbot

Open a new `tmux` window:

```
tmux
```

Install and run Hummingbot:

```bash tab="Option 1: Easy Install"
# 1) Download Hummingbot install script
wget https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/docker-commands/create.sh

# 2) Enable script permissions
chmod a+x create.sh

# 3) Run installation
./create.sh
```

```bash tab="Option 2: Manual Installation"
# 1) Create folder for your new instance
mkdir hummingbot_files

# 2) Create folders for log and config files
mkdir hummingbot_files/hummingbot_conf && mkdir hummingbot_files/hummingbot_logs

# 3) Launch a new instance of hummingbot
docker run -it \
--name hummingbot-instance \
--mount "type=bind,source=$(pwd)/hummingbot_files/hummingbot_conf,destination=/conf/" \
--mount "type=bind,source=$(pwd)/hummingbot_files/hummingbot_logs,destination=/logs/" \
coinalpha/hummingbot:latest
```

## Ubuntu

*Supported versions: 16.04 LTS, 18.04 LTS, 19.04*

#### Step 1: Install Docker

```bash tab="Option 1: Easy Install"
# 1) Download Docker install script
wget https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/install-docker/install-docker-ubuntu.sh

# 2) Enable script permissions
chmod a+x install-docker-ubuntu.sh

# 3) Run installation
./install-docker-ubuntu.sh

# **Note**: the script will close the terminal window
```

```bash tab="Option 2: Manual Installation"
# 1) Update Ubuntu's database of software
sudo apt-get update

# 2) Install tmux
sudo apt-get install -y tmux

# 3) Install Docker
sudo apt install -y docker.io

# 4) Start and Automate Docker
sudo systemctl start docker && sudo systemctl enable docker 

# 5) Change permissions for docker (optional)
# Allow docker commands without requiring sudo prefix
sudo usermod -a -G docker $USER 

# 6) Close terminal
exit
```

!!! warning "Restart terminal"
    The above commands will close your terminal window in order to enable the correct permissions for the `docker` command.  Open a new terminal window to proceed with [Step 2](#step-2-install-hummingbot).

#### Step 2: Install Hummingbot

Open a new `tmux` window:

```
tmux
```

Install and run Hummingbot:

```bash tab="Option 1: Easy Install"
# 1) Download Hummingbot install script
wget https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/docker-commands/create.sh

# 2) Enable script permissions
chmod a+x create.sh

# 3) Run installation
./create.sh
```

```bash tab="Option 2: Manual Installation"
# 1) Create folder for your new instance
mkdir hummingbot_files

# 2) Create folders for log and config files
mkdir hummingbot_files/hummingbot_conf && mkdir hummingbot_files/hummingbot_logs

# 3) Launch a new instance of hummingbot
docker run -it \
--name hummingbot-instance \
--mount "type=bind,source=$(pwd)/hummingbot_files/hummingbot_conf,destination=/conf/" \
--mount "type=bind,source=$(pwd)/hummingbot_files/hummingbot_logs,destination=/logs/" \
coinalpha/hummingbot:latest
```

## Debian

*Supported version: Debian GNU/Linux 9*

#### Step 1: Install Docker

```bash tab="Option 1: Easy Install"
# 1) Download Docker install script
wget https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/install-docker/install-docker-debian.sh

# 2) Enable script permissions
chmod a+x install-docker-debian.sh

# 3) Run installation
./install-docker-debian.sh

# **Note**: the script will close the terminal window
```

```bash tab="Option 2: Manual Installation"
# 1) Update package database
sudo apt update

# 2) Install dependencies
sudo apt install -y apt-transport-https ca-certificates curl gnupg2 software-properties-common tmux

# 3) Register Docker repository to your system
curl -fsSL https://download.docker.com/linux/debian/gpg | sudo apt-key add -
sudo add-apt-repository "deb [arch=amd64] https://download.docker.com/linux/debian $(lsb_release -cs) stable"
sudo apt update

# 4) Install Docker
sudo apt install -y docker-ce

# 5) Change permissions for docker (optional)
# Allow docker commands without requiring sudo prefix
sudo usermod -a -G docker $USER

# 6) Close terminal
exit
```

!!! warning "Restart terminal"
    The above commands will close your terminal window in order to enable the correct permissions for the `docker` command.  Open a new terminal window to proceed with [Step 2](#step-2-install-hummingbot_1).

#### Step 2: Install Hummingbot

Open a new `tmux` window:

```
tmux
```

Install and run Hummingbot:

```bash tab="Option 1: Easy Install"
# 1) Download Hummingbot install script
wget https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/docker-commands/create.sh

# 2) Enable script permissions
chmod a+x create.sh

# 3) Run installation
./create.sh
```

```bash tab="Option 2: Manual Installation"
# 1) Create folder for your new instance
mkdir hummingbot_files

# 2) Create folders for log and config files
mkdir hummingbot_files/hummingbot_conf && mkdir hummingbot_files/hummingbot_logs

# 3) Launch a new instance of hummingbot
docker run -it \
--name hummingbot-instance \
--mount "type=bind,source=$(pwd)/hummingbot_files/hummingbot_conf,destination=/conf/" \
--mount "type=bind,source=$(pwd)/hummingbot_files/hummingbot_logs,destination=/logs/" \
coinalpha/hummingbot:latest
```

## CentOS

*Supported version: 7*

#### Step 1: Install Docker

```bash tab="Option 1: Easy Install"
# 1) Download Docker install script
wget https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/install-docker/install-docker-centos.sh

# 2) Enable script permissions
chmod a+x install-docker-centos.sh

# 3) Run installation
./install-docker-centos.sh

# **Note**: the script will close the terminal window
```

```bash tab="Option 2: Manual Installation"
# 1) Update package database
sudo yum check-update

# 2) Install tmux
sudo yum -y install tmux

# 3) Install Docker
curl -fsSL https://get.docker.com/ | sh 

# 4) Start and Automate Docker
sudo systemctl start docker && sudo systemctl enable docker

# 5) Change permissions for docker (optional)
# Allow docker commands without requiring sudo prefix
sudo usermod -a -G docker $USER

# 6) Close terminal
exit
```

!!! warning "Restart terminal"
    The above commands will close your terminal window in order to enable the correct permissions for the `docker` command.  Open a new terminal window to proceed with [Step 2](#step-2-install-hummingbot_2).

#### Step 2: Install Hummingbot

Open a new `tmux` window:

```
tmux
```

Install and run Hummingbot:

```bash tab="Option 1: Easy Install"
# 1) Download Hummingbot install script
wget https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/docker-commands/create.sh

# 2) Enable script permissions
chmod a+x create.sh

# 3) Run installation
./create.sh
```

```bash tab="Option 2: Manual Installation"
# 1) Create folder for your new instance
mkdir hummingbot_files

# 2) Create folders for log and config files
mkdir hummingbot_files/hummingbot_conf && mkdir hummingbot_files/hummingbot_logs

# 3) Launch a new instance of hummingbot
docker run -it \
--name hummingbot-instance \
--mount "type=bind,source=$(pwd)/hummingbot_files/hummingbot_conf,destination=/conf/" \
--mount "type=bind,source=$(pwd)/hummingbot_files/hummingbot_logs,destination=/logs/" \
coinalpha/hummingbot:latest
```

----

## Developer Notes

- Additional details of the scripts can be found on [Github: Hummingbot Install with Docker](https://github.com/CoinAlpha/hummingbot/tree/development/installation/install-docker).