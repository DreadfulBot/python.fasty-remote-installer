import tarfile
import os
import sys
import paramiko
import math
import configparser
import ntpath

# config area
config_file = '.config.shared.ini'
root = os.path.abspath(os.path.dirname(os.path.abspath(__file__)))

# globals
entry_separator = None
excluded_files_list = None
archives_dir_name = None

# sftp stuff
transport = None
sftp_client = None

# ssh stuff
client = None

def path_leaf(path):
    head, tail = ntpath.split(path)
    return tail or ntpath.basename(head)

def read_config(config_file):
    if(not os.path.isfile(config_file)):
        raise FileNotFoundError('config file not found - ' + config_file)

    config = configparser.ConfigParser()
    config.read(config_file)
    return config

def check_argv():
    if len(sys.argv) < 2:
        raise EnvironmentError('usage: upload.py <mode>')

def get_upload_files(src_path, excluded_files_list):
    files_to_upload = []
    exclude = excluded_files_list

    for root, dirs, files in os.walk(src_path):
        dirs[:] = [d for d in dirs if d not in exclude]
        files[:] = [d for d in files if d not in exclude]
        for f in files:
            files_to_upload.append(os.path.relpath(os.path.join(root, f), src_path))

    return files_to_upload

def create_archive(files_root, files, arch_path):
    os.chdir(files_root)

    while os.path.isfile(arch_path):
        print('removing old archive')
        os.remove(arch_path)

    tf = tarfile.open(arch_path, "w:gz")

    try:
        for index, f in enumerate(files):
            current = math.ceil(index/math.ceil(len(files)/100))
            tf.add(f)
            print("compressed: {0}%".format(current), end="\n")

    finally:
        tf.close()

def get_mode_config_file_name():
    return '.env.'+sys.argv[1]+'.ini'

def load_mode_config(mode_config, i):
    mode_params = {
        'dpkg_script': mode_config.get('scripts', 'dpkg_script'),
        'dpkg_script_params': mode_config.get('scripts', 'dpkg_script_params'),
        'src_path': mode_config.get('dirs', 'src_path').split(entry_separator)[i],
        'upload_path': mode_config.get('dirs', 'upload_paths').split(entry_separator)[i],
        'install_script': mode_config.get('scripts', 'install_scripts').split(entry_separator)[i],
        'install_script_params': mode_config.get('scripts', 'install_scrpits_params').split(entry_separator)[i],
        'sftp_user': mode_config.get('sftp', 'sftp_user'),
        'sftp_password': mode_config.get('sftp', 'sftp_password'),
        'sftp_host': mode_config.get('sftp', 'sftp_host'),
        'sftp_port': int(mode_config.get('sftp', 'sftp_port'))
    }

    return mode_params

def load_config_file_params(config):
    global entry_separator, excluded_files_list, archives_dir_name
    entry_separator = config.get('system', 'entry_separator')
    excluded_files_list = config.get('system', 'excluded_files').split(entry_separator)
    archives_dir_name = config.get('system', 'archives_dir_name')


def connect_sftp(mode_config, transport, sftp_client):
    if(transport == None or sftp_client == None):
        transport = paramiko.Transport((mode_config['sftp_host'], mode_config['sftp_port']))
        transport.connect(username=mode_config['sftp_user'], password=mode_config['sftp_password'])
        sftp_client = paramiko.SFTPClient.from_transport(transport)

    return transport, sftp_client

def disconnect_sftp(sftp_client, transport):
    if(transport != None):
        transport.close()
        print('[x] disconnected transport')
    if(sftp_client != None):
        sftp_client.close()
        print('[x] disconnected sftp_client client')

def connect_ssh(mode_config, client):
    if(client == None):
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(
            hostname=mode_config['sftp_host'], 
            username=mode_config['sftp_user'], 
            password=mode_config['sftp_password'], 
            port=mode_config['sftp_port'])
    return client

def disconnect_ssh(client):
    if(client != None):
        client.close()
        print('[x] disconnected client')

def upload_files(sftp_client, transport, local_path, upload_path):
    sftp_client.put(local_path, upload_path, callback=print_totals)

def print_totals(transferred, to_be_transferred):
    current = math.ceil(transferred / (to_be_transferred / 100))
    print("transferred: {0}%".format(current), end="\n")

def exec_ssh_command(command, client):
    stdin, stdout, stderr = client.exec_command(command)
    exit_status = stdout.channel.recv_exit_status()

    if(exit_status != 0):
        raise ChildProcessError('failed to execute remote command ' + command + ' status: ' + str(exit_status))

    data = stdout.read() + stderr.read()
    return data.decode("utf-8") + '\n'

def replace_install_command_placeholders(params, install_command):
    command = install_command

    for key in ['installer_name', 'arch_name', 'mode', 'dpkg_script_name']:
        if key in params:
            command = command.replace('!{0}!'.format(key), params[key])

    return command

def cd_upload_path_command(params):
    return 'cd ' + params['upload_path'] + ';'

def print_formatted_command(command):
    print ('> ' + command + '\n')

# main
if __name__ == "__main__":
    try:

        check_argv()

        print('[x] loading config files...\n')

        print('[x] loading {0} config file\n'.format(config_file))

        shared_config = read_config(config_file)
        
        load_config_file_params(shared_config)

        print('[x] loading {0} config file\n'.format(get_mode_config_file_name()))

        mode_config = read_config(get_mode_config_file_name())

        for i in range(len(mode_config.get('dirs', 'src_path').split(entry_separator))):
            mode_config_params = load_mode_config(mode_config, i)
            upload_files_list = get_upload_files(mode_config_params['src_path'], excluded_files_list)

            arch_path = os.path.join(root, archives_dir_name, path_leaf(mode_config_params['src_path']) + '.tar.gz')
            create_archive(mode_config_params['src_path'], upload_files_list, arch_path)
            
            transport, sftp_client = connect_sftp(mode_config_params, transport, sftp_client)

            # upload archive
            print('[x] uploading files archive {0}\n'.format(path_leaf(arch_path)))
            upload_files(sftp_client, transport, arch_path, mode_config_params['upload_path'] + '/' + path_leaf(arch_path))

            # upload dpkg script
            print('[x] uploading dpkg script {0}\n'.format(path_leaf(mode_config_params['dpkg_script'])))
            upload_files(
                sftp_client, 
                transport, 
                os.path.join(root, mode_config_params['dpkg_script']),
                mode_config_params['upload_path'] + '/' + path_leaf(mode_config_params['dpkg_script']))

            # upload install script
            print('[x] uploading install script {0}\n'.format(path_leaf(mode_config_params['install_script'])))
            upload_files(
                sftp_client, 
                transport, 
                os.path.join(root, mode_config_params['install_script']), 
                mode_config_params['upload_path'] + '/' + path_leaf(mode_config_params['install_script']))

            client = connect_ssh(mode_config_params, client)

            # run dpkg script
            print('[x] running dpkg script\n')
            dpkg_command = 'cd ' + mode_config_params['upload_path'] + ';' + replace_install_command_placeholders(
                {
                    'dpkg_script_name' : path_leaf(mode_config_params['dpkg_script']),
                    'arch_name' : path_leaf(arch_path),
                    'mode' : sys.argv[1]
                },
                mode_config_params['dpkg_script_params']
            )
            
            print_formatted_command(dpkg_command)
            print(exec_ssh_command(dpkg_command, client))

            # run install script
            print('[x] running install script\n')
            install_command = cd_upload_path_command(mode_config_params) + replace_install_command_placeholders(
               {
                   'installer_name' : path_leaf(mode_config_params['install_script']),
                   'arch_name' : path_leaf(arch_path),
                   'mode' : sys.argv[1]
               },
               mode_config_params['install_script_params']
            )
            
            print_formatted_command(install_command)
            print(exec_ssh_command(install_command, client))

            # clear scripts
            ## remove archive

            ### local
            os.remove(arch_path)

            ### remote
            clear_command = '{0} rm {1};'.format(cd_upload_path_command(mode_config_params), path_leaf(arch_path))

            print_formatted_command(clear_command)
            print(exec_ssh_command(clear_command, client))

            ## remove dpkg script
            clear_command = '{0} rm {1};'.format(cd_upload_path_command(mode_config_params), path_leaf(mode_config_params['dpkg_script']))

            print_formatted_command(clear_command)
            print(exec_ssh_command(clear_command, client))

            ## remove install script
            clear_command = '{0} rm {1};'.format(cd_upload_path_command(mode_config_params), path_leaf(mode_config_params['install_script']))

            print_formatted_command(clear_command)
            print(exec_ssh_command(clear_command, client))

    except Exception as ex:
        print(ex)
        disconnect_sftp(sftp_client, transport)
        disconnect_ssh(client)