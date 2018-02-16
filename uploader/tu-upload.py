import tarfile
import os
import sys
import paramiko
import math

# configuration area
prefix = 'tu-'
srcRelPath=os.path.realpath(os.environ['src_rel_path'])
rootPath= os.path.dirname(os.path.abspath(__file__))
localPath = os.path.join(rootPath, srcRelPath)
archName = prefix + 'blog.tar.gz'
installerName = prefix + 'install.php'

# here you can set all files, that will be
# excluded from result archive
excludedFiles = [
    'bower_components',
    'node_modules',
    archName,
    'muse_manifest.xml',
    prefix + 'upload.py',
    prefix + 'init-env.bat',
    prefix + 'install.sh',
    installerName]

# configuration data from env .bat script
hostAddress = os.environ['ftp_host']
hostPath = os.environ['ftp_path']
hostUser = os.environ['ftp_user']
hostPassword = os.environ['ftp_password']

def getUploadFiles():
    result = []
    exclude = excludedFiles

    for root, dirs, files in os.walk(localPath):
        dirs[:] = [d for d in dirs if d not in exclude]
        files[:] = [d for d in files if d not in exclude]
        for f in files:
            result.append(os.path.relpath(os.path.join(root, f), localPath))

    return result

def compressFile(files, archName):
    os.chdir(localPath)

    while os.path.isfile(archName):
        print("removing old archive")
        os.remove(archName)
        
    tf = tarfile.open(archName, "w:gz")

    try:
        for index, f in enumerate(files):
            current = math.ceil(index/math.ceil(len(files)/100))
            tf.add(f)
            print("\rcompressed: {0}%".format(current), end="")

    finally:
        tf.close()

def connectSftp():
    t = paramiko.Transport((hostAddress, 22))
    t.connect(username=hostUser, password=hostPassword)

    sftp = paramiko.SFTPClient.from_transport(t)
    return t, sftp

def disconnectSftp(sftpClient, transport):
    transport.close()
    sftpClient.close()

def uploadFiles(localPath, remotePath):
    transport, sftpClient = connectSftp()
    try:
        sftpClient.put(localPath, remotePath, callback=printTotals)
    except:
        disconnectSftp(sftpClient, transport)

def printTotals(transferred, toBeTransferred):
    current = math.ceil(transferred / (toBeTransferred / 100))
    print("\rtransferred: {0}%".format(current), end="")

def execSshCommand(command):
    client = None
    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(hostname=hostAddress, username=hostUser, password=hostPassword, port=22)

        stdin, stdout, stderr = client.exec_command(command)
        data = stdout.read() + stderr.read()
        return data.decode("utf-8")
    except:
        if(client != None):
            client.close()
    finally:
        if(client != None):
            client.close()

def runInstall():
    print(execSshCommand('cd ' + hostPath + ';php ' + installerName + ' ' + archName))
    print(execSshCommand('cd ' + hostPath + ';rm ' + installerName))
    print(execSshCommand('cd ' + hostPath + ';rm ' + archName))

def clearLocal(file):
    print("[x] all junk files were cleared. Have a nice day!\n")
    os.remove(file)


if __name__ == "__main__":
    print('[x] creating zip file ... ')

    files = getUploadFiles()
    compressFile(files, os.path.join(rootPath, archName))

    print('\nOK')

    print('[x] connecting to sftp-server ... ')

    print('OK')

    print('[x] uploading files data ... ')

    uploadFiles(os.path.join(rootPath, archName), hostPath + '/' + archName)

    print('\nOK')

    print('[x] uploading installer data ... ')

    uploadFiles(os.path.join(rootPath, installerName), hostPath + '/' + installerName)

    print('\nOK')

    print('[x] running install script on server ...')

    runInstall()

    print ('\nOK')

    clearLocal(os.path.join(rootPath, archName))

    print('[x] all tasks executed!')