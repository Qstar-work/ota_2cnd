# android二次打包工具使用说明



## 运行环境

本工具支持windows和linux系统的运行。具体要求：

* Windows系统：本工具不支持XP，需要在XP以上系统环境下运行。无须额外安装，所需工具已打包在tool文件夹中。
* Linux系统：需要确保系统能正常使用python3.x和java8.0。



## 使用方法

1. 把需要二次打包的zip文件放在工具的根目录下，然后改名为rom.zip

2. （可选操作）支持更换开机静态logo。logo 格式要求为 24位 bmp 格式，以及（1280*720）的分辨率。如需修改，请命名为bootlogo.bmp 复制到custom目录下。

3. （可选操作）支持修改build信息。在打开custom文件夹下的build.conf文件，根据需要修改相应的配置信息。如需要更改版本信息时，打开文件后查找`ro.fw.pck.version`，修改对应的值，修改后格式如：`ro.fw.pck.version=7.3.0.0`，注意版本要需要由4组数字构成。

   常用的配置信息如下，可通过#进行注释：

   ```
   ro.fw.pck.version=7.3.0.0 # 版本号
   
   # platform.has_advance_set=false # 是否显示高级设置
   
   # ro.product.model=OTT-4216 #显示的机型信息
   # ro.product.manufacturer=OTT連網機上盒 #显示的机型信息
   # ro.checkdevice.on=true  #升级是否校验型号
   # ro.product.locale=zh-TW #默认语言
   # ro.product.locale.language=zh #默认语言
   # ro.product.region=TW #默认地区
   
   # persist.sys.timezone=Asia/Taipei #默认时区
   # persist.sys.country=TW #默认地区
   # persist.sys.language=zh #默认语言
   
   # pre.displayration=95 #默认重显率
   # platform.isModelShow=false #设置是否显示model；
   ```

   

4. （可选操作）支持删除已预制的APP。在打开custom文件夹下的delete-app.conf文件，根据需要填写将被删除的apk名称，所输入的apk名称大小写均可，且不需要输入.apk后缀。

   配置参考如下，可通过#进行注释，如需要删除，则把该行#取消：

   ```
   #Chrome
   #FZCAPlugin
   #Netflix
   #QuickPic
   #rkmusic_s
   #youtube
   #Xbmc
   ```

   

   

5. （可选操作）支持自定义替换。如果需要替换或增加zip里面的内容，以custom -> rom这文件夹作为根目录，把需要替换或新增内容，放在对应的路径上。如需要新增预制APP时，可在custom -> rom -> system -> preinstall-private目录下，放在apk即可。

6. （可选操作）支持更换签名。签名文件放在tool -> keys下面，根据需要按名称直接替换即可。

7. 完成以上可选操作后，Windows环境点击run.bat文件，Linux环境点击run.sh文件。点击后工具将开始运行，打包完成后，将输出在out文件夹下，名称为update.zip。

