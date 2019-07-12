# Install Hummingbot in the Cloud

Using Hummingbot as a long running service can be achieved with the help of cloud platforms such as Google Cloud Platform, Amazon Web Services, and Microsoft Azure.

Below, we show you how to set up a new Virtual Machine Instance on each major cloud platform.

## Google Cloud Platform

   * Navigate to the Google Cloud Platform console
   * Create an instance of Compute Instance
   * Select “New VM Instance”, then pick `Ubuntu 18.04 LTS`

   ![Create New Instance](/assets/img/gcp-new-vm.png)

   * Click on "SSH" to SSH into the newly created VM instance

![Connect SSH](/assets/img/gcp-ssh.png)

## Amazon Web Services

   * Navigate to the AWS Management Console
   * Click on "Launch a Virtual Machine"

   ![Create New Instance](/assets/img/aws1.png)

   * Select `Ubuntu Server 18.04 LTS (HVM)`

   ![Select Server Type](/assets/img/aws2.png)

   * Click on "Review and Launch", and then "Launch"

   ![Select Instance Type](/assets/img/aws3.png)

   * Select “create a new key pair”, name the key pair (e.g. hummingbot), download key pair, and then click on “Launch Instances”.

   ![Create a New Key Pair](/assets/img/aws4.png)

   * Click on “View Instances”

   * To connect to the instance from the terminal, click on “Connect” and then follow the instructions on the resulting page.

   ![Connect to AWS Instance](/assets/img/aws5.png)

## Microsoft Azure

   * Navigate to the Virtual Machines console.
   * Click on the "Add" button in the top-left corner.

   ![Create New Instance](/assets/img/azure1.png)

   * Choose a name for the resource group and for the VM itself.
   * Select `Ubuntu 18.04 LTS` for the image type and `Standard D2s v3` for the size.

   ![Select Server Type](/assets/img/azure2.png)

   * Under "Administrator Account", choose password and select a username and password.
   * Under "Inbound Port Rules", select SSH and HTTP.

   ![Configure Server Protocols](/assets/img/azure3.png)

   * Scroll up to the top and click on "Management" tab.
   * Choose a valid name for your diagnostics storage account.

   ![Set Up Diagnostics](/assets/img/azure4.png)

   * Go to the "Review and Create" tab, click on "Create".

   ![Create the Virtual Machine](/assets/img/azure5.png)

   * While your VM is being created, download and install PuTTY for your OS.

   ![Download and Install PuTTY](/assets/img/azure6.png)

   * After your VM has been initialized, copy the public IP address.
   * Open the PuTTY app and paste the IP address into the host name, then open.

   ![Connect to Azure Instance](/assets/img/azure7.png)

---
# Next: [Install Hummingbot for Linux](/installation/linux)