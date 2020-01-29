# Common 'How To' Questions

Frequently asked 'how-to' questions and problems that may arise when using Hummingbot.

#### How to find out where the config and log files are on Hummingbot installed via Docker

Run the following command to view the details of your instance:

```bash
docker inspect $instance_name
```

Look for a field `Mounts`, which will describe where the folders are on you local machine:

```
"Mounts": [
    {
        "Type": "bind",
        "Source": "/home/ubuntu/hummingbot_files/hummingbot_data",
        "Destination": "/data",
        "Mode": "",
        "RW": true,
        "Propagation": "rprivate"
    },
    {
        "Type": "bind",
        "Source": "/home/ubuntu/hummingbot_files/hummingbot_conf",
        "Destination": "/conf",
        "Mode": "",
        "RW": true,
        "Propagation": "rprivate"
    },
    {
        "Type": "bind",
        "Source": "/home/ubuntu/hummingbot_files/hummingbot_logs",
        "Destination": "/logs",
        "Mode": "",
        "RW": true,
        "Propagation": "rprivate"
    }
],
```

!!! note
    Read through [Log File Management](https://docs.hummingbot.io/utilities/logging/) for more information.

#### How to edit the conf files or access the log files used by my docker instance?

If Hummingbot is installed on a virtual machine or a Linux cloud server, you can use the `vi` text editor (or any text editor of your choice). Run command `vi $filename`. See [this page](https://www.tipsandtricks-hq.com/unix-vi-commands-take-advantage-of-the-unix-vi-editor-374) for more information how to use this text editor.

You can also use an FTP client software (e.g. WinSCP, FileZila) to copy, move, files and folders from your virtual machine to your local machine and vice versa.


#### How to copy and paste in Docker Toolbox (Windows)

By default, the Docker Toolbox has copy and paste disabled within the command line. This can make it difficult to port long API and wallet keys to Hummingbot. However, there is a simple fix which can be enabled as follows:

1. Open the Docker Toolbox via the Quickstart Terminal</br></br>
  ![](/assets/img/docker_toolbox_startup.PNG)</br></br>
2. Right-click on the title bar of Toolbox and select "Properties"</br></br>
  ![](/assets/img/docker_toolbox_properties.png)</br></br>
3. Check the box under the "Options" tab to enable "Ctrl Key Shortcuts"</br></br>
  ![](/assets/img/docker_toolbox_enable.png)

Close any warnings, and you're done! Just hit enter to move onto the next line and you should be able to copy and paste text using **Ctrl+Shift+C** and **Ctrl+Shift+V**.


#### Paste items from clipboard in PuTTY

You should be able to paste items from your clipboard by doing mouse right-click or `SHIFT + right-click`. If that doesn't work, follow the steps below.

1. If you are currently logged in a session, left-click on the upper left hand corner of the PuTTY window or a right-click anywhere on the title bar then select "Change Settings". If not, proceed to next step.
2. In PuTTY configuration under Window category go to "Selection". Select the "Window" radio button for action of mouse buttons.
3. You can now paste items from clipboard by doing a right-click to bring up the menu and select "Paste".

![](/assets/img/putty_copy_paste.gif)

#### Other ways to copy and paste

Copying to clipboard on Windows or Linux:

```
Ctrl + C 
Ctrl + Insert
Ctrl + Shift + C
```

Pasting items from clipboard on Windows or Linux:

```
Ctrl + V
Shift + Insert
Ctrl + Shift + V
```

#### Locate data folder or hummingbot_trades.sqlite when running Hummingbot via Docker

1. Find ID of your running container.
```
# Display list of containers
docker container ps -a

# Start a docker container
docker container start <PID>
```
2. Evaluate containers file system.
```
run docker exec -t -i <name of your container> /bin/bash
```
3. Show list using `ls` command.
4. Switch to `data` folder and use `ls` command to display content.
5. If you would like to remove the sqlite database, use `rm <database_name>` command.

In version 0.22.0 release, we updated the Docker scripts to map the `data` folder when creating and updating an instance.

1. Delete the old scripts.
```
rm create.sh update.sh
```
2. Download the updated scripts.
```
wget https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/docker-commands/create.sh
wget https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/docker-commands/update.sh
```
3. Enable script permissions.
```
chmod a+x *.sh
```
4. Command `./create.sh` creates a new Hummingbot instance.
5. Command `./update.sh` updates an existing Hummingbot instance.


#### Get REST API data using Postman

Some information related to an exchange can be retrieved through their public API such as minimum order sizes. You can download a program called [Postman](https://www.getpostman.com/) and follow the instructions in [Get Started with Postman](https://learning.getpostman.com/getting-started/).

![](/assets/img/postman.png)


#### How to reset in case of forgotten password

For security reasons, Hummingbot does not store your password anywhere so there's no way to recover it. The only solution is to create a new password and re-enter your API keys upon restarting Hummingbot after deleting or moving the encrypted files.

1. Run `exit` command to exit from the Hummingbot client.
2. Delete the encrypted files and wallet key file (if applicable) from the `hummingbot_conf` folder.
3. Restart Hummingbot and run `config` command.

If using Linux, copy the commands below and run in your terminal to delete the files. You will be prompted to confirm before proceeding.

```
rm hummingbot_files/hummingbot_conf/encrypted* hummingbot_files/hummingbot_conf/key_file*
```

If Hummingbot is installed on Windows, simply delete these files found in `%localappdata%\hummingbot.io\Hummingbot`.

!!! warning
    Be careful when deleting the local wallet key file created through Hummingbot i.e. wallet that was not imported from Metamask. Deleting the its key file will result in permanently lose your funds in that wallet.

![delete_encrypted_files](/assets/img/ts_delete_encrypted.gif)


#### Transfer files from/to Windows Subsystem for Linux and local computer

Execute command `explorer.exe .` (make sure to include the dot) in WSL to launch a file explorer window of your current directory. Then you will be able to move, copy and delete files like you normally would on a Windows computer.


#### Download a previous version of Hummingbot in Windows

1. Go to `https://hummingbot-distribution.s3.amazonaws.com/`. It will show an XML file with all the Hummingbot versions listed.</br></br>
    ![binary_distribution](/assets/img/ts_binary_distribution.png)</br></br>
2. To download a previous version, add the version inside `<Key>` after the URL.

For example, enter the URL</br>
https://hummingbot-distribution.s3.amazonaws.com/hummingbot_v0.20.0_setup.exe
</br>on your web browser to start downloading the installer for 0.20.0 version.