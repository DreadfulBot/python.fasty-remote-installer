import tarfile
import os
import sys
import paramiko
import math
import configparser

# configuration area
configFile = 'config.ini'
rootPath = os.path.dirname(os.path.abspath(__file__))

# some sftpClient stuff
transport = 0
sftpClient = 0
client = 0

# reading env variables
def readEnv():
    try:
        global hostAddress, hostPath, hostUser, hostPassword,\
            localPath, srcRelPath

        env_src_rel_path = config.get('system', 'env_src_rel_path')
            
        if (env_src_rel_path not in os.environ):
            raise EnvironmentError('src_rel_path not detected in env')

        srcRelPath = os.environ[env_src_rel_path]

        localPath = os.path.join(rootPath, srcRelPath)

        env_ftp_host_name = config.get('system', 'env_ftp_host_name')
        env_ftp_path_name = config.get('system', 'env_ftp_path_name')
        env_ftp_user_name = config.get('system', 'env_ftp_user_name')
        env_ftp_password_name = config.get('system', 'env_ftp_password_name')

        if(env_ftp_host_name not in os.environ or
                env_ftp_path_name not in os.environ or
                env_ftp_user_name not in os.environ or
                env_ftp_password_name not in os.environ
            ):
            raise EnvironmentError('ftp parameter is missing')

        hostAddress = os.environ[env_ftp_host_name]
        hostPath = os.environ[env_ftp_path_name]
        hostUser = os.environ[env_ftp_user_name]
        hostPassword = os.environ[env_ftp_password_name]
        return 1
    except EnvironmentError as error:
        print(error)
        return -1


# reading all config information from file %configFile%
# in configuration area
def readConfig():
    try:
        global prefix, \
            archName, installerName, excludedFiles, \
            installerCommands, installerNames, installerParams, \
            config, envFilePrefix

        config = configparser.ConfigParser()
        config.read(configFile)

        prefix = config.get('system', 'prefix')
        envFilePrefix = config.get('system', 'env_file_prefix')

        archName = prefix + config.get('system', 'archive_name')

        excludedFiles = config.get('system', 'excluded_files').split(',')

        installerNames = [prefix + n for n in config.get('system', 'installer_names').split(',')]
        installerCommands = config.get('system', 'installer_commands').split(',')
        installerParams = config.get('system', 'installer_params').split(',')

        return 0
    except EnvironmentError as error:
        print(error)
        return -1

# generate list of files for uploading from %srcFilePath%
# and excluding files from %excludeFilesList% list
def getUploadFiles(srcFilePath, excludeFilesList):
    result = []
    exclude = excludeFilesList

    for root, dirs, files in os.walk(srcFilePath):
        dirs[:] = [d for d in dirs if d not in exclude]
        files[:] = [d for d in files if d not in exclude]
        for f in files:
            result.append(os.path.relpath(os.path.join(root, f), srcFilePath))

    return result

# compress all fils from list %files% to %archName%
def compressFile(files, archName):
    os.chdir(localPath)

    while os.path.isfile(archName):
        print('removing old archive')
        os.remove(archName)

    tf = tarfile.open(archName, "w:gz")

    try:
        for index, f in enumerate(files):
            current = math.ceil(index/math.ceil(len(files)/100))
            tf.add(f)
            print("\rcompressed: {0}%".format(current), end="")

    finally:
        tf.close()

# connectiong over sftpClient protocol
def connectSftp(transport, sftpClient):
    if(transport == 0 or sftpClient == 0):
        transport = paramiko.Transport((hostAddress, 22))
        transport.connect(username=hostUser, password=hostPassword)
        sftpClient = paramiko.SFTPClient.from_transport(transport)

    return transport, sftpClient

def disconnectSftp(sftpClient, transport):
    if(transport != 0):
        transport.close()
        print('[x] disconnected transport')
    if(sftpClient != 0):
        sftpClient.close()
        print('[x] disconnected sftpClient client')


# connectiong over ssh protocol
def connectSsh(client):
    if(client == 0):
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(hostname=hostAddress, username=hostUser, password=hostPassword, port=22)
    return client

def disconnetcSsh(client):
    if(client != 0):
        client.close()
        print('[x] disconnected client')


def uploadFiles(localPath, remotePath):
    try:
        sftpClient.put(localPath, remotePath, callback=printTotals)
    except:
        disconnectSftp(sftpClient, transport)

def printTotals(transferred, toBeTransferred):
    current = math.ceil(transferred / (toBeTransferred / 100))
    print("\rtransferred: {0}%".format(current), end="")


def execSshCommand(command, client):
    try:
        print('> exec ' + command)
        stdin, stdout, stderr = client.exec_command(command)
        exit_status = stdout.channel.recv_exit_status()

        if(exit_status != 0):
            raise ChildProcessError('failed to execute remote command ' + command + ' status: ' + str(exit_status))

        data = stdout.read() + stderr.read()
        return data.decode("utf-8")
    except ChildProcessError as error:
        disconnetcSsh(client)
        print(error)

def runInstall(installerNames, installerCommands, installerParams):
    for i in range(0, len(installerNames)):

        installer = installerNames[i]
        command = installerCommands[i]
        params = installerParams[i]

        print('[x] running script ' + installer)

        paramsConcat = ''
        for p in params.split(';'):
            if(p == '!archName!'):
                paramsConcat += ' ' + archName
            else:
                paramsConcat += ' ' + p
        
        print(execSshCommand('cd ' + hostPath + ';' + command + ' ' + installer + paramsConcat, client))
            

def clearLocal(file):
    os.remove(file)

def clearRemote(file):
    print(execSshCommand('cd ' + hostPath + ';rm ' + file, client))

    for i in range(0, len(installerNames)):
        print(execSshCommand('cd ' + hostPath + ';rm ' + installerNames[i], client))

if __name__ == "__main__":
    try:
        print('[x] reading startup parameters ...')

        print('[x] reading config file ... ')

        if(readConfig() < 0):
            raise ImportError ('config read error')

        print('[x] reading env variables ...')
        if(readEnv() < 0):
            raise EnvironmentError('reading env error')

        print('[x] creating zip file ... ')

        files = getUploadFiles(localPath, excludedFiles)

        compressFile(files, os.path.join(rootPath, archName))

        print(' OK')

        print('[x] connecting to sftpClient-server ... ')

        transport, sftpClient = connectSftp(transport, sftpClient)

        print('OK')

        print('[x] uploading files data ... ')

        uploadFiles(os.path.join(rootPath, archName), hostPath + '/' + archName)

        print(' OK')

        print('[x] uploading installer data ... ')

        for installerName in installerNames:
            uploadFiles(os.path.join(rootPath, installerName), hostPath + '/' + installerName)

        print(' OK')

        print('connecting over SSH')

        client = connectSsh(client)

        print('OK')

        print('[x] running install script on server ...')

        runInstall(installerNames, installerCommands, installerParams)

        print ('OK')

        clearLocal(os.path.join(rootPath, archName))

        print('[x] all local junk files were cleared!')

        clearRemote(archName)

        print('[x] all remote junk files were cleared!')

        print('[x] all tasks executed!')

        disconnetcSsh(client)
        disconnectSftp(sftpClient, transport)

        print('[x] exec finished')

    except Exception as ex:
        print(ex)