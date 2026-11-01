# 网页界面

React页面沿用来源项目的布局与交互，实时页接本项目PC后台，离线页接独立账户/记录业务。原文件归属与导入身份见[来源说明](../NOTICE.md)。

从项目根执行 `./build/build_web.ps1`；依赖和构建输出写 `tmp/web_frontend`，不要在正式源码目录安装node_modules。构建后通过 `src/web/run.py` 同源提供网页和API；开发代理配置在vite.config.ts。使用与限制见[网页教程](../../../docs/download_guide.md)。

Waveform使用原始采样时刻及可选缺口标记，抽稀不改变事件坐标；实时页面与导入历史共用该组件。页面不启动QRS、CNN或训练，分类缺失不能填成正常。
