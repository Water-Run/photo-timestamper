# 照片时间水印添加器

`WaterRun`  

> 开源于[GitHub](https://github.com/Water-Run/photo-timestamper)  

![软件图标, 使用NanoBananaPro生成](assets/readme-logo.png)

`照片时间水印添加器`(`photo-timestamper`)是一个简单的Windows桌面端应用, 用于为照片添加时间水印.  

核心特点是提供**模拟相机原厂风格的水印预设**: 比如`佳能`风格等等.  
项目使用`PyQT6`, 辅助`Claude Opus 4.5`开发, 并使用`pyinstaller`打包为`.exe`.  

> 由于采用单文件的模式打包, 启动时消耗较多时间是正常的  

![示例图](./assets/demo.png)

## 安装和使用  

从***[下载](https://github.com/Water-Run/photo-timestamper/releases/tag/photo-timestamper)***下载`photo-timestamper.zip`并解压, 运行`照片时间水印添加器.exe`即可.  

> 开源于[GitHub](https://github.com/Water-Run/photo-timestamper)  

*或从源码自行构建:*  

```cmd
python build.py
```

程序的使用很简单:  

### 水印风格  

`照片时间水印添加器`预设了多个预设水印, 包括契合相机原厂的风格:

- `佳能`  

- `尼康`  

- `索尼`  

- `松下`  

- `富士`  

- `宾得`  

- `小米`

- `默认黄`  

- `默认白`  

- `默认红`  

- `默认绿`  

- `默认蓝`  

- `默认灰`  

- `默认紫`  
