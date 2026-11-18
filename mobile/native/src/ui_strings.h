#ifndef BB10_RECORDER_UI_STRINGS_H
#define BB10_RECORDER_UI_STRINGS_H

#include <QString>

inline QString recorderLabel(const QString &lang, const QString &key) {
    const bool en = (lang == "en");
    if (key == "app_title") return en ? "BB10 Call Recorder" : QString::fromUtf8("BB10 通话录音");
    if (key == "tagline") return en ? "100% offline local call recording · Zero network permissions" : QString::fromUtf8("纯本地离线通话录音 · 零联网权限");
    if (key == "close") return en ? "Close" : QString::fromUtf8("关闭");
    if (key == "recordings") return en ? "Recordings" : QString::fromUtf8("录音列表");
    if (key == "settings") return en ? "Settings" : QString::fromUtf8("设置");
    if (key == "refresh") return en ? "Refresh" : QString::fromUtf8("刷新");
    if (key == "install_service") return en ? "Activate Background Service" : QString::fromUtf8("安装并启动录音后台");
    if (key == "start_manual") return en ? "Start Recording Current Call" : QString::fromUtf8("立即录制当前通话");
    if (key == "stop_manual") return en ? "Stop Recording" : QString::fromUtf8("停止本次录音");
    if (key == "consent_title") return en ? "Call Recording Notice" : QString::fromUtf8("通话录音合规提示");
    if (key == "consent_body") return en
        ? "Recordings are saved strictly on your phone storage (/accounts/1000/shared/voice). Please comply with local laws regarding call consent."
        : QString::fromUtf8("所有录音文件仅保存在本机闪存或 SD 卡，绝不联网上传。开启前请确认遵守所在地关于通话录音知情同意的法规。");
    if (key == "consent_accept") return en ? "I Understand & Enable" : QString::fromUtf8("已知悉并开启");
    if (key == "status_uninstalled") return en ? "Service Not Installed" : QString::fromUtf8("后台服务尚未安装");
    if (key == "status_recording") return en ? "Recording Active Call..." : QString::fromUtf8("正在录制当前通话…");
    if (key == "status_ready_auto") return en ? "Auto-Record Ready" : QString::fromUtf8("自动录音已就绪");
    if (key == "status_ready_manual") return en ? "Manual Mode Ready" : QString::fromUtf8("手动录音模式已就绪");
    if (key == "status_disabled") return en ? "Recording Paused" : QString::fromUtf8("通话录音已暂停");
    if (key == "volte_tap_on") return en ? "VoLTE Digital Dual-Channel: Enabled" : QString::fromUtf8("VoLTE 纯数字双向缓冲：已开启");
    if (key == "volte_tap_off") return en ? "Audio Source: QSA Enhanced Mic (+18 dB)" : QString::fromUtf8("当前音源：QSA 增强麦克风（+18 dB）");
    if (key == "enable_volte_tap") return en ? "Enable VoLTE Digital Buffer" : QString::fromUtf8("开启 VoLTE 纯数字内录协同");
    if (key == "disable_volte_tap") return en ? "Disable VoLTE Digital Buffer" : QString::fromUtf8("关闭 VoLTE 纯数字内录协同");
    if (key == "play") return en ? "Play" : QString::fromUtf8("播放");
    if (key == "stop_play") return en ? "Stop" : QString::fromUtf8("停止");
    if (key == "delete") return en ? "Delete" : QString::fromUtf8("删除");
    if (key == "empty_list") return en ? "No call recordings yet." : QString::fromUtf8("暂无通话录音记录。");
    if (key == "auto_record") return en ? "Automatically record connected calls" : QString::fromUtf8("通话接通后自动开始录音");
    if (key == "storage_title") return en ? "Storage Location" : QString::fromUtf8("录音存储位置");
    if (key == "storage_internal") return en ? "Phone Shared Voice Folder" : QString::fromUtf8("手机内置共享目录（voice）");
    if (key == "storage_sd") return en ? "Removable SD Card" : QString::fromUtf8("外置 SD 存储卡");
    if (key == "include_number") return en ? "Keep full caller number in metadata" : QString::fromUtf8("记录完整号码（关闭则脱敏显示）");
    if (key == "language") return en ? "Language" : QString::fromUtf8("界面语言");
    if (key == "uninstall") return en ? "Uninstall Background Service" : QString::fromUtf8("卸载后台服务（保留录音文件）");

    if (key == "support_kicker") return en ? "OCTOLAB / INDEPENDENT · SOURCE AVAILABLE" : QString::fromUtf8("OCTOLAB / 独立制作 · 源码公开");
    if (key == "support_title") return en ? "Keep your BlackBerry\ngoing a little longer." : QString::fromUtf8("让老黑莓\n再多用一阵。");
    if (key == "support_story") return en
        ? "A small tool for those who still love a physical keyboard.\nMade by OctoLab, refined with the community."
        : QString::fromUtf8("为仍然喜欢实体键盘的你，做一点小工具。\n由 OctoLab 制作，和社区一起慢慢打磨。");
    if (key == "support_star") return en ? "GitHub · Star" : QString::fromUtf8("GitHub · 加星");
    if (key == "support_studio") return en ? "By OctoLab" : QString::fromUtf8("OctoLab 出品");
    if (key == "support_volte") return en ? "Sister Project · BB10 VoLTE" : QString::fromUtf8("姊妹项目 · BB10 VoLTE 官网");
    if (key == "support_star_note") return en ? "Leave a Star on the project if you like it. That helps too." : QString::fromUtf8("打开项目后，可以亲手点一颗 Star。也是一种支持。");
    if (key == "support_coffee") return en ? "Buy the maker a coffee" : QString::fromUtf8("请作者喝杯咖啡");
    if (key == "support_coffee_close") return en ? "Close coffee options" : QString::fromUtf8("收起咖啡心意");
    if (key == "support_optional") return en
        ? "Only if you feel like it. Free for personal noncommercial use; commercial use requires a paid license."
        : QString::fromUtf8("喜欢的话，随意就好。个人非商业使用免费；商业用途须另获付费授权（打赏不构成商业授权）。");
    if (key == "support_alipay") return en ? "Alipay" : QString::fromUtf8("支付宝");
    if (key == "support_wechat") return en ? "WeChat" : QString::fromUtf8("微信");
    if (key == "support_amount") return en ? "Your choice" : QString::fromUtf8("一点心意");
    if (key == "support_custom") return en ? "Choose your own amount" : QString::fromUtf8("自选金额");
    if (key == "support_qr") return en ? "Maker's payment QR code" : QString::fromUtf8("作者的收款二维码");
    if (key == "support_scan_custom") return en
        ? "Scan with another phone and enter your amount. Check the recipient and amount in your payment app."
        : QString::fromUtf8("用另一台手机扫码，自行填写金额。请在支付应用中核对收款人和金额。");
    if (key == "support_scan_fixed") return en
        ? "Scan with another phone. Check the recipient and selected amount in your payment app."
        : QString::fromUtf8("用另一台手机扫码。请在支付应用中核对收款人和所选金额。");
    if (key == "support_opening") return en ? "Opening your browser…" : QString::fromUtf8("正在打开浏览器…");
    if (key == "support_opened") return en
        ? "Sent to your browser. If the page cannot load, copy the link to another device."
        : QString::fromUtf8("已交给浏览器打开。若页面无法加载，可复制链接到其他设备。");
    if (key == "support_open_failed") return en ? "Could not open the browser. You can copy the link below." : QString::fromUtf8("未能打开浏览器。可以复制下面的链接。");
    if (key == "support_copy") return en ? "Copy link" : QString::fromUtf8("复制链接");
    if (key == "support_copied") return en ? "Link copied." : QString::fromUtf8("链接已复制。");
    if (key == "support_copy_failed") return en ? "Could not copy. Use the link shown above." : QString::fromUtf8("复制失败，请使用上方显示的链接。");
    return key;
}

#endif
