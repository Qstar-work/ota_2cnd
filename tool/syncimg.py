#!/usr/bin/python

import os
import shutil
import zipfile
import subprocess
import platform
import time
import re
import datetime
import tempfile
from xml.dom.minidom import parseString

SEGMENT = "+"
LINE_SEGMENT = "+" * 64

LOCAL_BASE_DIR = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))

ROM_PATH = os.path.join(LOCAL_BASE_DIR, 'DargonFace', 'fsop', 'system')
CUSTOM_DIR = os.path.join(LOCAL_BASE_DIR, 'custom')
ROM_DIR = os.path.join(LOCAL_BASE_DIR, 'DargonFace', 'fsop')

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


def _sync_bootlogo():
    print('检查 bootlogo 是否存在')
    from_file = os.path.join(CUSTOM_DIR, 'bootlogo.bmp')
    to_dir = os.path.join(ROM_DIR, 'lhsfile', 'bootlogo.bmp')

    if not os.path.exists(from_file):
        print('bootlogo.bmp 不存在: %s' % from_file)
        return

    print('复制文件: %s' % from_file)
    shutil.copyfile(from_file, to_dir)
    to_dir = os.path.join(ROM_DIR, 'bootfs', 'bootlogo.bmp')
    shutil.copyfile(from_file, to_dir)
    to_dir = os.path.join(tempfile.gettempdir(), 'bootlogo.lhs')
    print('复制文件: %s' % to_dir)
    shutil.copyfile(from_file, to_dir)	
    print('bootlogo 更新完成')

    print('检查 bootanimation.zip 是否存在')	
    from_file = os.path.join(CUSTOM_DIR, 'rom', 'system', 'media', 'bootanimation.zip')
    if os.path.exists(from_file):
        to_dir = os.path.join(ROM_DIR, 'lhsfile', 'bootanimation.zip')
        print('复制文件: %s' % from_file)
        shutil.copyfile(from_file, to_dir)
        print('bootanimation.zip 更新完成')


def _check_permission():
    build_prop_path = os.path.join(ROM_DIR, 'system', 'build.prop')
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
    from_dir = os.path.join(CUSTOM_DIR, 'rom', 'system')
    to_dir = ROM_PATH
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
            os.makedirs(os.path.dirname(to_file_path), exist_ok=True)
            shutil.copyfile(from_file_path, to_file_path)
            print('复制文件: %s' % file_name)


def delete_apps():
    print('准备删除APP')
    file_path = os.path.join(CUSTOM_DIR, 'delete-app.conf')
    app_dir = os.path.join(ROM_DIR, 'system', 'preinstall-private')
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

def delete_files():
    print('准备删除文件')
    file_path = os.path.join(CUSTOM_DIR, 'delete-files.conf')
    with open(file_path) as file:
        for line in file.readlines():
            if line.startswith('#'): continue
            delete_app_path = os.path.join(ROM_DIR, line)
            if os.path.exists(delete_app_path): 
                if os.path.isdir(delete_app_path):
                    shutil.rmtree(delete_app_path, ignore_errors=True)
                else: 
                    os.remove(delete_app_path)
    print('APP删除文件')

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
    build_prop_path = os.path.join(ROM_DIR, 'system', 'build.prop')
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
		
    from_file = os.path.join(ROM_DIR, 'system', 'build.prop')
    to_dir = os.path.join(ROM_DIR, 'lhsfile', 'build.prop')
    shutil.copyfile(from_file, to_dir)
    to_dir = os.path.join(LOCAL_BASE_DIR, 'out')
    os.makedirs(to_dir, exist_ok=True)
    to_dir = os.path.join(to_dir, 'build.prop')
    shutil.copyfile(from_file, to_dir)
    print('完成build.prop修改')

def read_prop_line(row, pattern):
    if not row: return
    row = row.strip()
    if not row or row.startswith('#'): return
    search_value = re.findall(pattern, row)
    if not search_value: return
    search_value = search_value[0]
    return search_value


def modify_dtv():
    dtv_path = os.path.join(ROM_DIR, 'system', 'etc', 'dtv', 'dtv.xml')
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


def syncimg():
    try:
        print('\n'.join([
            LINE_SEGMENT,
            SEGMENT + ' ' * 12 + '欢迎使用Img包同步工具（基于android 7.0)' + ' ' * 12 + SEGMENT,
            LINE_SEGMENT,
        ]))
        print('工具开始运行...')
        if not os.path.exists(ROM_PATH): raise PackError('错误: DargonFace 没导入img文件镜像')
        _check_permission()
        _sync_bootlogo()
        delete_apps()
        delete_files()
        copy_system()
        modify_build_prop()
        modify_dtv()
        print('同步数据到DargonFace img镜像完成，可以保存新的img镜像')
    except PackError as error:
        if error.hidden:
            print(error)
        else:
            raise error
    except:
        import traceback
        print(traceback.format_exc())


if __name__ == '__main__':
    syncimg()
