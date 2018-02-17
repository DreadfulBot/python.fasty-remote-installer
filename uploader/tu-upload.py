import tarfile
import os
import sys
import paramiko
import math
import configparser

# configuration area
configFile = 'tu-config.ini'
rootPath= os.path.dirname(os.path.abspath(__file__))

def readConfig():
    try:
        global prefix, srcRelPath, localPath, \
            archName, installerName, excludedFiles, \
            hostAddress, hostPath, hostUser, hostPassword, \
            installerCommands, installerNames, installerParamsCounter

        config = configparser.ConfigParser()
        config.read(configFile)

        prefix = config.get('system', 'prefix')

        archName = prefix + config.get('system', 'archive_name')

        excludedFiles = config.get('system', 'excluded_files').split(',')

        installerNames = [prefix + n for n in config.get('system', 'installer_names').split(',')]
        installerCommands = config.get('system', 'installer_commands').split(',')
        installerParamsCounter = config.get('system', 'installer_params_counter').split(',')

        excludedFiles.append(archName)
        excludedFiles.append(prefix + config.get('system', 'init_env_script'))
        excludedFiles.append(prefix + config.get('system', 'config_file_name'))
        excludedFiles.append(os.path.basename(__file__))

        if (os.environ['src_rel_path'] == None):
            raise EnvironmentError('src_rel_path not detected in env')

        srcRelPath = os.environ['src_rel_path']

        localPath = os.path.join(rootPath, srcRelPath)

        if(os.environ['ftp_host'] == None or
               os.environ['ftp_path'] == None or
               os.environ['ftp_user'] == None or
               os.environ['ftp_password'] == None
           ):
            raise EnvironmentError('ftp parameter is missing')

        hostAddress = os.environ['ftp_host']
        hostPath = os.environ['ftp_path']
        hostUser = os.environ['ftp_user']
        hostPassword = os.environ['ftp_password']

        return 0
    except EnvironmentError as error:
        print(error)
        return -1

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

        print('> exec ' + command)
        stdin, stdout, stderr = client.exec_command(command)
        exit_status = stdout.channel.recv_exit_status()

        if(exit_status != 0):
            raise ChildProcessError('failed to execute remote command ' + command + ' status: ' + str(exit_status))

        data = stdout.read() + stderr.read()
        return data.decode("utf-8")
    except ChildProcessError as error:
        print(error)
    finally:
        if(client != None):
            client.close()

def runInstall():
    for i in range(0, len(installerNames)):

        installer = installerNames[i]
        command = installerCommands[i]
        paramsCounter = int(installerParamsCounter[i])

        print('[x] running script ' + installer)

        if i == 0 and paramsCounter == 1:
            print(execSshCommand('cd ' + hostPath + ';' + command + ' ' + installer + ' ' + archName))
        else:
            print(execSshCommand('cd ' + hostPath + ';' + command + ' ' + installer))

def clearLocal(file):
    os.remove(file)

def clearRemote(file):
    print(execSshCommand('cd ' + hostPath + ';rm ' + file))

    for i in range(0, len(installerNames)):
        print(execSshCommand('cd ' + hostPath + ';rm ' + installerNames[i]))

if __name__ == "__main__":
    try:
        print('[x] reading config file ... ')

        if(readConfig() < 0):
            raise ImportError ('config read error')

        print('[x] creating zip file ... ')

        files = getUploadFiles()

        compressFile(files, os.path.join(rootPath, archName))

        print('\nOK\n')

        print('[x] connecting to sftp-server ... ')

        print('\nOK\n')

        print('[x] uploading files data ... ')

        uploadFiles(os.path.join(rootPath, archName), hostPath + '/' + archName)

        print('\nOK\n')

        print('[x] uploading installer data ... ')

        for installerName in installerNames:
            uploadFiles(os.path.join(rootPath, installerName), hostPath + '/' + installerName)

        print('\nOK\n')

        print('[x] running install script on server ...\n')

        runInstall()

        print ('\nOK\n')

        clearLocal(os.path.join(rootPath, archName))

        print("[x] all local junk files were cleared!\n")

        clearRemote(archName)

        print("[x] all remote junk files were cleared!\n")

        print('[x] all tasks executed!')

    except ImportError as error:
        print(error)