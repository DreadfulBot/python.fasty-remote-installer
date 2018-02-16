**python.fasty-remote-installer**

**REQUIREMENTS**
* python 3.6.x

**DEPENDENCIES**
```python
import tarfile
import os
import sys
import paramiko
import math
```

**FOR WHAT**
* For automatic and fast uploading files to remote ftp/sftp host

**HOW**

Due development process, there is need to upload a lot of small project files to remote server. It is rather slow process over ssh protocol.

As i noticed, it is much more faster to send one large file than many small files. This idea lay down in philosophy of that python script.

*Main idea is:* compress all needed files in tar.gz archive, send them over ftp/sftp protocol to remote server, send php-installation script for decompressing it, run this sent script on remote host. That's all.

**USAGE**

Script needs some env-variables to be set. All required variables are in *tu-init-env.bat* script file:

```cmd
# ftp user nickname
set ftp_user= 

# ftp user password
set ftp_password=

# ip-address/hostname of target host
set ftp_host=

# absolute path for directory, where compressed files and installer
# script will be placed
set ftp_path=

# relative path (relatively to .py-scrypt) of local files
# that shoud be compressed and sent to remote host
set src_rel_path=../build
```

So, to use this script you need:
* set env variables (windows users can run *tu-init-env.bat* in cmd)
* run *tu-upload.py* with python 3.6.x
* wait operation be finished

