## Binary (Mac/Win)

To update Hummingbot, uninstall Hummingbot locally from your computer, then download and install the latest version from the website https://hummingbot.io/download/

Users can revert and update Hummingbot installed via Binary by following the steps below:

To install a previous Hummingbot version via binary, download the installer from https://hummingbot.io/download/ in the previous client section

![](/assets/img/installer.png)

Users can also download an older version not listed on the website using the URL format `https://dist.hummingbot.io/[hummingbot_version]`

For example:

![](/assets/img/download.png)


## Docker

Hummingbot is regularly updated each month (see [Release Notes](/release-notes/)) and recommends users to periodically update their installations to get the latest version of the software.

Updating to the latest docker image (e.g. `coinalpha/hummingbot:latest`)

!!! note
    Make sure to stop all the containers using the same image first  before running the `./update.sh` script.

=== "Scripts"

    ```bash
    # 1) Remove old script
    rm -rf update.sh

    # 2) Download update script
    wget https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/docker-commands/update.sh

    # 3) Enable script permissions
    chmod a+x update.sh

    # 4) Run script to update hummingbot
    ./update.sh
    ```

=== "Manual"

    ```bash
    # 1) Delete instance
    docker rm hummingbot-instance

    # 2) Delete old hummingbot image
    docker image rm coinalpha/hummingbot:latest

    # 3) Re-create instance with latest hummingbot release
    docker run -it \
    --network host \
    --name hummingbot-instance \
    --mount "type=bind,source=$(pwd)/hummingbot_files/hummingbot_conf,destination=/conf/" \
    --mount "type=bind,source=$(pwd)/hummingbot_files/hummingbot_logs,destination=/logs/" \
    --mount "type=bind,source=$(pwd)/hummingbot_files/hummingbot_data,destination=/data/" \
    coinalpha/hummingbot:latest
    ```
A previous version (i.e. `version-0.30.0`) can be installed when creating a Hummingbot instance.

## Source

The Hummingbot codebase is hosted at https://github.com/coinalpha/hummingbot.

=== "Scripts"

    ```bash
    # 1) Download update script to the *root* folder
    wget https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/install-from-source/update.sh

    # 2) Enable script permissions
    chmod a+x update.sh

    # 3) Run script to update hummingbot
    ./update.sh
    ```

=== "Manual"

    ```bash
    # From the hummingbot root folder:
    git pull origin master

    # Recompile the code:
    conda deactivate
    ./uninstall
    ./clean
    ./install
    conda activate hummingbot
    ./compile
    bin/hummingbot.py
    ```

