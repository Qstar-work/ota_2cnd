#!/usr/bin/python

import os
import shutil
import zipfile
import subprocess
import platform
import time
import re
import datetime
from xml.dom.minidom import parseString

SEGMENT = "+"
LINE_SEGMENT = "+" * 64

LOCAL_BASE_DIR = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))

ROM_PATH = os.path.join(LOCAL_BASE_DIR, 'rom.zip')
SIGN_APK_JAR_PATH = os.path.join(LOCAL_BASE_DIR, 'tool', 'signapk.jar')
KEYS_DIR = os.path.join(LOCAL_BASE_DIR, 'tool', 'keys')
UNSIGN_ROM_DIR = os.path.join(LOCAL_BASE_DIR, 'out', 'unsign-rom')
UNSIGN_ROM_PATH = os.path.join(LOCAL_BASE_DIR, 'out', 'unsign-rome.zip')
SIGNED_UPDATE_FILE = os.path.join(LOCAL_BASE_DIR, 'out', 'update.zip')
CUSTOM_DIR = os.path.join(LOCAL_BASE_DIR, 'custom')
ROM_DIR = os.path.join(CUSTOM_DIR, 'rom')

# add for logo build
PC_TOOLS_DIR = os.path.join(LOCAL_BASE_DIR, 'tool', 'pctools')
PACK_FEX_DIR = os.path.join(LOCAL_BASE_DIR, 'tool', 'pack_fex')


class PackError(Exception):

    def __init__(self, message, hidden=False):
        super().__init__(message)
        self.hidden = hidden


if 'window' in platform.system().lower():
    JAVA_HOME = os.path.join(LOCAL_BASE_DIR, 'tool', 'openjdk8', 'bin', 'java.exe')
    FS_BUILD_PATH = os.path.join(PC_TOOLS_DIR, 'windows', 'fsbuild200', 'fsbuild.exe')
else:
    JAVA_HOME = 'java'
    FS_BUILD_PATH = os.path.join(PC_TOOLS_DIR, 'linux', 'fsbuild200', 'fsbuild')


def _unzip_file(file_path, out_path):
    print('准备解压: %s' % file_path)
    with zipfile.ZipFile(file_path, mode='r', compression=zipfile.ZIP_DEFLATED) as file:
        file.extractall(out_path)
    print('解压完毕，输出: %s' % out_path)


def _zip_dir(in_path, out_path):
    print('准备压缩: %s' % in_path)
    if os.path.exists(out_path) and os.path.isfile(out_path): os.remove(out_path)
    with zipfile.ZipFile(out_path, mode='a', compression=zipfile.ZIP_DEFLATED) as file:
        for dir_info in os.walk(in_path):
            for file_name in dir_info[2]:
                if file_name == '.DS_Store': continue
                file_path = os.path.join(dir_info[0], file_name)
                file.write(file_path, arcname=file_path.replace(in_path, ''))
    print('压缩完毕, 输出: %s' % out_path)


def _sign_cmd(pem, pk8, in_path, out_path):
    return '%s -jar %s -w %s %s %s %s' % (JAVA_HOME, SIGN_APK_JAR_PATH, pem, pk8, in_path, out_path)


def _sign_apk_cmd(in_path, out_path):
    pem = os.path.join(KEYS_DIR, 'platform.x509.pem')
    pk8 = os.path.join(KEYS_DIR, 'platform.pk8')
    return _sign_cmd(pem, pk8, in_path, out_path)


def _sign_rom_cmd(in_path, out_path):
    pem = os.path.join(KEYS_DIR, 'releasekey.x509.pem')
    pk8 = os.path.join(KEYS_DIR, 'releasekey.pk8')
    return _sign_cmd(pem, pk8, in_path, out_path)


def _sign_update_zip(unsign_zip_path, signed_zip_path):
    print('进行zip签名')
    cmd = _sign_rom_cmd(unsign_zip_path, signed_zip_path)
    process = subprocess.Popen(cmd, shell=True, stdin=subprocess.PIPE)
    time.sleep(3)
    print('\nzip签名中...')
    process.communicate('\n'.encode())
    print('\nzip签名完毕')

def _build_bootlogo():
    print('检查 bootlogo 是否存在')
    boot_res_dir = os.path.join(PACK_FEX_DIR, 'boot-resource')
    from_file = os.path.join(CUSTOM_DIR, 'bootlogo.bmp')
    to_dir = os.path.join(boot_res_dir, 'bootlogo.bmp')

    if not os.path.exists(from_file):
        print('bootlogo.bmp 不存在: %s' % from_file)
        return

    print('复制文件: %s' % from_file)
    shutil.copyfile(from_file, to_dir)

    print('开始生成新的bootloader.fex')
    pwdold = os.getcwd()
    print('pwd saved %s' % pwdold)
    os.chdir(PACK_FEX_DIR)
    pwdnew = os.getcwd()
    INI_FILE = os.path.join(PACK_FEX_DIR, 'ini_config', 'boot-resource.ini')
    cmd_build = '%s %s split_xxxx.fex' % (FS_BUILD_PATH, INI_FILE)
    process = subprocess.Popen(cmd_build, shell=True, stdin=subprocess.PIPE)
    process.wait()
    os.chdir(pwdold)

    res_fex = os.path.join(PACK_FEX_DIR, 'boot-resource.fex')
    rom_fex_path = os.path.join(ROM_DIR, 'bootloader.fex')
    if not os.path.exists(res_fex):
        print('boot-resource.fex 不存在: %s' % res_fex)
        return
    shutil.move(res_fex, rom_fex_path)
    print('bootlogo 更新完成')


def _check_permission():
    build_prop_path = os.path.join(UNSIGN_ROM_DIR, 'system', 'build.prop')
    pattern = re.compile(r'([._a-zA-Z0-9]*)=([^#\s]*)[\s#]?.?', re.S)
    checked_keys = set({'ro.fw.pck.version',
                        'ro.fw.pck.product',
                        'ro.fw.pck.customer'})
    file_keys = set()
    with open(build_prop_path) as file:
        for row in file.readlines():
            search_value = read_prop_line(row, pattern)
            if not search_value:
                continue
            file_keys.add(search_value[0])
    if not (checked_keys & file_keys == checked_keys):
        raise PackError('Unknown Error: -9', True)


def copy_system():
    from_dir = ROM_DIR
    to_dir = UNSIGN_ROM_DIR
    if not os.path.exists(from_dir):
        print('rom文件夹不存在: %s' % from_dir)
        return
    if not os.path.exists(to_dir):
        print('rom.zip解压文件夹不存在: %s' % to_dir)
        return
    for dir_info in os.walk(from_dir):
        for file_name in dir_info[2]:
            if file_name == '.DS_Store': continue
            from_file_path = os.path.join(dir_info[0], file_name)
            to_file_path = to_dir + from_file_path.replace(from_dir, '')
            shutil.copyfile(from_file_path, to_file_path)
            print('复制文件: %s' % file_name)


def delete_apps():
    print('准备删除APP')
    file_path = os.path.join(CUSTOM_DIR, 'delete-app.conf')
    app_dir = os.path.join(UNSIGN_ROM_DIR, 'system', 'preinstall-private')
    app_list = []
    with open(file_path) as file:
        for line in file.readlines():
            line = line.replace('\n', '').replace('\r', '').replace('.apk', '').strip()
            if line.startswith('#'): continue
            app_list.append(line.lower())
    app_list = set(app_list)
    for dir_info in os.walk(app_dir):
        for file_name in dir_info[2]:
            if file_name == '.DS_Store': continue
            name = file_name.lower()
            if name.endswith('.apk'): name = name.replace('.apk', '')
            if name not in app_list: continue
            delete_app_path = os.path.join(dir_info[0], file_name)
            os.remove(delete_app_path)
            print('已删除App: %s' % file_name)

    print('APP删除完毕')


def modify_build_prop():
    print('准备修改build.prop')
    file_path = os.path.join(CUSTOM_DIR, 'build.conf')
    modify_dict = {'ro.product.builddate': datetime.datetime.now().strftime('%d/%m/%Y')}
    pattern = re.compile(r'([._a-zA-Z0-9]*)=([^#\s]*)[\s#]?.?', re.S)
    with open(file_path, mode='r', encoding='UTF-8') as file:
        for row in file.readlines():
            search_value = read_prop_line(row, pattern)
            if not search_value: continue
            modify_dict[search_value[0]] = search_value[1]
    out_data = []
    build_prop_path = os.path.join(UNSIGN_ROM_DIR, 'system', 'build.prop')
    with open(build_prop_path) as file:
        for row in file.readlines():
            search_value = read_prop_line(row, pattern)
            if search_value:
                key = search_value[0]
                pop_value = modify_dict.pop(key, None)
                if pop_value:
                    out_data.append('%s=%s\n' % (key, pop_value))
                else:
                    out_data.append(row)
            else:
                out_data.append(row)
    if modify_dict:
        out_data.append('# Additional build properties from custom/build.conf\n')
        for key, value in modify_dict.items():
            out_data.append('%s=%s\n' % (key, value))
    out_data = ''.join(out_data)
    with open(build_prop_path, mode='w') as file:
        file.write(out_data)
    print('完成build.prop修改')

def modify_version_info():
    print('准备修改version_info')
    file_path = os.path.join(CUSTOM_DIR, 'build.conf')
    modify_list = ['ro.fw.pck.version','ro.fw.pck.product','ro.fw.pck.customer']
    modify_dict = {}
    pattern = re.compile(r'([._a-zA-Z0-9]*)=([^#\s]*)[\s#]?.?', re.S)
    with open(file_path, mode='r', encoding='UTF-8') as file:
        for row in file.readlines():
            search_value = read_prop_line(row, pattern)
            if not search_value: continue
            if search_value[0] in modify_list: modify_dict[search_value[0]] = search_value[1]
    out_data = []
    build_prop_path = os.path.join(UNSIGN_ROM_DIR, 'META-INF', 'version_info')
    with open(build_prop_path) as file:
        for row in file.readlines():
            search_value = read_prop_line(row, pattern)
            if search_value:
                key = search_value[0]
                pop_value = modify_dict.pop(key, None)
                if pop_value:
                    out_data.append('%s=%s\n' % (key, pop_value))
                else:
                    out_data.append(row)
            else:
                out_data.append(row)
    if modify_dict:
        out_data.append('# Additional build properties from custom/build.conf\n')
        for key, value in modify_dict.items():
            out_data.append('%s=%s\n' % (key, value))
    out_data = ''.join(out_data)
    with open(build_prop_path, mode='w') as file:
        file.write(out_data)
    print('完成version_info修改')

def read_prop_line(row, pattern):
    if not row: return
    row = row.strip()
    if not row or row.startswith('#'): return
    search_value = re.findall(pattern, row)
    if not search_value: return
    search_value = search_value[0]
    return search_value


def modify_dtv():
    dtv_path = os.path.join(UNSIGN_ROM_DIR, 'system', 'etc', 'dtv', 'dtv.xml')
    file_path = os.path.join(CUSTOM_DIR, 'dtv.conf')
    if not os.path.exists(dtv_path) or not os.path.exists(file_path): return
    print('准备修改dtv.xml')
    modify_dict = {}
    pattern = re.compile(r'([_a-zA-Z0-9]*)=([^#\s]*)[\s#]?.?', re.S)
    with open(file_path) as file:
        for row in file.readlines():
            search_value = read_prop_line(row, pattern)
            if not search_value:
                continue
            key = search_value[0]
            modify_dict[key] = (re.compile(r'%s=(\"[^#\s]*\")' % key, re.S),
                                '%s=%s' % (key, search_value[1]))
    with open(dtv_path) as file:
        content = file.read()
    content = re.sub(re.compile(r'(<!--.*-->)', re.S), '', content)
    for key, (pattern, value) in modify_dict.items():
        if key in content:
            content = re.sub(pattern, value, content)
        else:
            content = content.replace('<dtv', '<dtv\n\t%s' % value)
    with open(dtv_path, mode='w') as file:
        file.write(content)
    print('dtv.xml修改完毕')


def pack():
    try:
        print('\n'.join([
            LINE_SEGMENT,
            SEGMENT + ' ' * 12 + '欢迎使用自动打包工具（基于android 7.0)' + ' ' * 12 + SEGMENT,
            LINE_SEGMENT,
        ]))
        print('工具开始运行...')
        if not os.path.exists(ROM_PATH): raise PackError('错误: rom.zip文件不在当前目录')
        if os.path.exists(UNSIGN_ROM_DIR): shutil.rmtree(UNSIGN_ROM_DIR, ignore_errors=True)
        if os.path.exists(UNSIGN_ROM_PATH): os.remove(UNSIGN_ROM_PATH)
        os.makedirs(UNSIGN_ROM_DIR, exist_ok=True)
        _unzip_file(ROM_PATH, UNSIGN_ROM_DIR)
        _check_permission()
        _build_bootlogo()
        delete_apps()
        copy_system()
        modify_build_prop()
        modify_version_info()
        modify_dtv()
        # 打包zip
        if os.path.exists(UNSIGN_ROM_PATH): os.remove(UNSIGN_ROM_PATH)
        _zip_dir(UNSIGN_ROM_DIR, UNSIGN_ROM_PATH)
        # 签名zip
        _sign_update_zip(UNSIGN_ROM_PATH, SIGNED_UPDATE_FILE)
        if os.path.exists(UNSIGN_ROM_DIR): shutil.rmtree(UNSIGN_ROM_DIR, ignore_errors=True)
        if os.path.exists(UNSIGN_ROM_PATH): os.remove(UNSIGN_ROM_PATH)
        print('打包完毕，输出目录: %s' % SIGNED_UPDATE_FILE)
    except PackError as error:
        if error.hidden:
            print(error)
        else:
            raise error
    except:
        import traceback
        print(traceback.format_exc())


if __name__ == '__main__':
    pack()
