"""User-friendly bilingual Windows/Desktop helper for BB10 Call Recorder."""
import argparse
import json
from pathlib import Path
import queue
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox
import webbrowser

from bar_installer import BUNDLED_BAR_REL
from desktop_paths import desktop_release_version, resource_root
from ssh_deploy import inspect_full_phone, install_all, stage_and_run

BG = '#F5F4EF'
CARD = '#FFFFFF'
BORDER = '#DFDDD4'
PRIMARY = '#233D32'
PRIMARY_ACTIVE = '#1A2E26'
TEXT = '#1F2924'
MUTED = '#5C6B63'
WARN = '#8A4B18'

STRINGS = {
    'zh': {
        'window_title': 'BB10 通话录音 · 桌面安装助手',
        'subtitle': '纯本地离线通话录音 · 零联网权限 · 原生 BB10 播放',
        'octolab_btn': 'OctoLab · 支持与打赏',
        'lang_btn': 'English',
        'conn_card': '手机连接与当前状态',
        'check_btn': '检测手机状态',
        'choose_ssh_btn': '选择 SSH 配置…',
        'not_checked': '尚未检测手机。若本机已使用过 BB10 VoLTE 配对手机，可直接点击「检测手机状态」或「一键安装」。',
        'checking': '正在通过 USB-SSH 检测手机状态…',
        'installing_all': '正在向手机安装「BB10 通话录音」桌面图标并启用自动录音后台（约需 15–30 秒）…',
        'installing_svc': '正在更新手机端后台录音服务…',
        'toggling_tap': '正在切换 VoLTE 纯数字双向缓冲配置…',
        'action_card': '一键安装与管理',
        'install_all_btn': '一键安装手机 App 与开启自动录音（推荐）',
        'install_svc_btn': '仅安装 / 更新后台录音服务',
        'toggle_tap_on': '开启 VoLTE 纯数字双向内录协同',
        'toggle_tap_off': '关闭 VoLTE 纯数字双向内录协同',
        'where_btn': '如何查看与导出录音文件？',
        'tip_sachesi': '提示：您也可以无需配对 SSH，直接用 Sachesi / Darcy BBTools 安装发布包中的 .bar 文件，再在手机上打开「BB10 通话录音」点一次激活。',
        'where_title': '录音文件保存位置',
        'where_body': (
            '所有通话录音均保存为 BB10 原生可直接播放的 16 kHz WAV 文件：\n\n'
            '• 手机文件管理器路径：\n'
            '  设备（Device）/ voice / bb10-call-recorder/\n'
            '  （完整系统路径：/accounts/1000/shared/voice/bb10-call-recorder）\n\n'
            '• 在手机上：可直接打开「BB10 通话录音」App 点击播放，或在系统自带「文件管理器 -> 语音」中点击播放。\n'
            '• 导出到电脑：开启黑莓「设置 -> 存储和访问 -> USB 访问 / Wi-Fi 共享」后，打开 voice/bb10-call-recorder 文件夹即可直接复制。'
        ),
        'ok_installed_all': '安装完成！「BB10 通话录音」图标已添加到黑莓桌面，自动通话录音后台已就绪。',
        'ok_installed_svc': '后台录音服务已更新并启动。',
        'err_prefix': '操作未完成：',
        'err_no_ssh': '未找到已配对的 BB10 Root SSH 配置。请先用 BB10 VoLTE 完成手机连接配对，或直接用 Sachesi 安装 .bar 文件后在手机端激活。',
        'support_title': 'OctoLab · 独立制作与支持',
        'support_heading': '让老黑莓，再多用一阵。',
        'support_story': '为仍然喜欢实体键盘的你，做一点纯粹、克制的小工具。\n由 OctoLab 制作，源码公开，100% 离线运行，无任何联网权限。',
        'support_star': 'GitHub · 点亮 Star',
        'support_studio': 'OctoLab 官网',
        'support_volte': '姊妹项目 · BB10 VoLTE',
        'support_coffee': '请作者喝杯咖啡（自愿打赏）',
        'support_alipay': '支付宝 Alipay',
        'support_wechat': '微信支付 WeChat',
        'support_custom': '自选金额',
        'support_note': '个人非商业使用永久免费；商业用途须联系 octoooo@octoooo.com 获取付费授权（打赏不构成商业授权）。',
        'close': '关闭',
    },
    'en': {
        'window_title': 'BB10 Call Recorder · Desktop Helper',
        'subtitle': '100% Offline Local Call Recording · Zero Network Permissions · Native Playback',
        'octolab_btn': 'OctoLab · Support & Coffee',
        'lang_btn': '中文',
        'conn_card': 'Phone Connection & Live Status',
        'check_btn': 'Check Phone',
        'choose_ssh_btn': 'Select SSH Config…',
        'not_checked': 'Phone not checked yet. If this PC is already paired via BB10 VoLTE, click "Check Phone" or "One-Click Install".',
        'checking': 'Checking rooted BB10 phone over USB-SSH…',
        'installing_all': 'Installing "BB10 Call Recorder" home-screen app and enabling auto-recording (15–30s)…',
        'installing_svc': 'Updating background recording daemon on phone…',
        'toggling_tap': 'Updating VoLTE digital dual-channel buffer setting…',
        'action_card': 'One-Click Setup & Controls',
        'install_all_btn': 'One-Click Install Phone App & Enable Auto-Record (Recommended)',
        'install_svc_btn': 'Install / Update Background Service Only',
        'toggle_tap_on': 'Enable VoLTE Digital Dual-Channel Buffer',
        'toggle_tap_off': 'Disable VoLTE Digital Dual-Channel Buffer',
        'where_btn': 'Where Are My Recordings Saved?',
        'tip_sachesi': 'Tip: You can also sideload the .bar file directly with Sachesi / Darcy BBTools without SSH, then tap Activate inside the phone app.',
        'where_title': 'Recording Storage & Export',
        'where_body': (
            'All call recordings are saved as standard 16 kHz WAV files playable natively on BB10:\n\n'
            '• On-phone File Manager path:\n'
            '  Device / voice / bb10-call-recorder/\n'
            '  (Full path: /accounts/1000/shared/voice/bb10-call-recorder)\n\n'
            '• On your phone: Play directly inside the "BB10 Call Recorder" app or via BB10 File Manager.\n'
            '• Copy to PC: Enable USB Mass Storage / Wi-Fi File Sharing in BB10 Settings -> Storage and Access, then open voice/bb10-call-recorder.'
        ),
        'ok_installed_all': 'Installed! "BB10 Call Recorder" is now on your BB10 home screen and auto-recording is active.',
        'ok_installed_svc': 'Background recording service updated and running.',
        'err_prefix': 'Action incomplete: ',
        'err_no_ssh': 'No paired BB10 Root SSH config found on this PC. Pair once via BB10 VoLTE, select an ssh_config file, or sideload the .bar with Sachesi.',
        'support_title': 'OctoLab · Story & Coffee Tip',
        'support_heading': 'Keep your BlackBerry going a little longer.',
        'support_story': 'A small, focused offline utility for people who still love physical keyboards.\nMade by OctoLab · Source available · Zero internet permissions.',
        'support_star': 'GitHub · Star Repo',
        'support_studio': 'OctoLab Studio',
        'support_volte': 'Sister Project · BB10 VoLTE',
        'support_coffee': 'Buy the maker a coffee (Optional)',
        'support_alipay': 'Alipay',
        'support_wechat': 'WeChat Pay',
        'support_custom': 'Custom',
        'support_note': 'Free for personal noncommercial use. Commercial use requires a paid license via octoooo@octoooo.com.',
        'close': 'Close',
    },
}


class RecorderDesktopApp:
    def __init__(self, root_win):
        self.root = root_win
        self.res_root = resource_root()
        self.project = json.loads((self.res_root / 'project.json').read_text(encoding='utf-8'))
        self.release_ver = desktop_release_version(self.project)
        self.lang = 'zh'
        self.busy = False
        self.custom_ssh = ''
        self.last_status = None
        self.queue = queue.Queue()
        self._images = {}

        self.root.configure(bg=BG)
        self.root.geometry('760x580')
        self.root.minsize(680, 520)
        icon_ico = self.res_root / 'assets/app.ico'
        if icon_ico.is_file():
            try:
                self.root.iconbitmap(str(icon_ico))
            except Exception:
                pass

        self._build_ui()
        self._apply_lang()
        self.root.after(50, self._poll_queue)

    def t(self, key):
        return STRINGS[self.lang][key]

    def _load_image(self, rel_path):
        if rel_path not in self._images:
            full = self.res_root / rel_path
            if full.is_file():
                self._images[rel_path] = tk.PhotoImage(file=str(full))
            else:
                self._images[rel_path] = None
        return self._images[rel_path]

    def _build_ui(self):
        top = tk.Frame(self.root, bg=BG, padx=24, pady=18)
        top.pack(fill='x')

        title_col = tk.Frame(top, bg=BG)
        title_col.pack(side='left', fill='x', expand=True)
        self.lbl_title = tk.Label(title_col, font=('Segoe UI', 16, 'bold'), fg=PRIMARY, bg=BG, anchor='w')
        self.lbl_title.pack(fill='x')
        self.lbl_sub = tk.Label(title_col, font=('Segoe UI', 9), fg=MUTED, bg=BG, anchor='w')
        self.lbl_sub.pack(fill='x', pady=(2, 0))

        btn_col = tk.Frame(top, bg=BG)
        btn_col.pack(side='right')
        self.btn_octo = tk.Button(
            btn_col, command=self.open_support_dialog,
            bg=PRIMARY, fg='#FFFFFF', activebackground=PRIMARY_ACTIVE, activeforeground='#FFFFFF',
            relief='flat', padx=12, pady=6, font=('Segoe UI', 9, 'bold'), cursor='hand2',
        )
        self.btn_octo.pack(side='left', padx=(0, 8))
        self.btn_lang = tk.Button(
            btn_col, command=self.toggle_language,
            bg=CARD, fg=TEXT, relief='solid', bd=1, padx=10, pady=5, font=('Segoe UI', 9), cursor='hand2',
        )
        self.btn_lang.pack(side='left')

        # Status Card
        self.card_conn = tk.Frame(self.root, bg=CARD, highlightbackground=BORDER, highlightthickness=1, padx=20, pady=16)
        self.card_conn.pack(fill='x', padx=24, pady=(0, 14))

        conn_hdr = tk.Frame(self.card_conn, bg=CARD)
        conn_hdr.pack(fill='x')
        self.lbl_conn_hdr = tk.Label(conn_hdr, font=('Segoe UI', 11, 'bold'), fg=PRIMARY, bg=CARD)
        self.lbl_conn_hdr.pack(side='left')

        self.btn_ssh = tk.Button(
            conn_hdr, command=self.choose_ssh_config,
            bg=BG, fg=TEXT, relief='flat', padx=10, pady=4, font=('Segoe UI', 9), cursor='hand2',
        )
        self.btn_ssh.pack(side='right', padx=(6, 0))
        self.btn_check = tk.Button(
            conn_hdr, command=self.check_phone,
            bg=BG, fg=PRIMARY, relief='solid', bd=1, padx=12, pady=4, font=('Segoe UI', 9, 'bold'), cursor='hand2',
        )
        self.btn_check.pack(side='right')

        self.lbl_status = tk.Label(
            self.card_conn, font=('Segoe UI', 10), fg=TEXT, bg=CARD,
            justify='left', anchor='w', wraplength=670,
        )
        self.lbl_status.pack(fill='x', pady=(12, 0))

        # Actions Card
        self.card_act = tk.Frame(self.root, bg=CARD, highlightbackground=BORDER, highlightthickness=1, padx=20, pady=16)
        self.card_act.pack(fill='both', expand=True, padx=24, pady=(0, 20))

        self.lbl_act_hdr = tk.Label(self.card_act, font=('Segoe UI', 11, 'bold'), fg=PRIMARY, bg=CARD, anchor='w')
        self.lbl_act_hdr.pack(fill='x', pady=(0, 12))

        self.btn_install_all = tk.Button(
            self.card_act, command=self.run_install_all,
            bg=PRIMARY, fg='#FFFFFF', activebackground=PRIMARY_ACTIVE, activeforeground='#FFFFFF',
            relief='flat', pady=10, font=('Segoe UI', 10, 'bold'), cursor='hand2',
        )
        self.btn_install_all.pack(fill='x', pady=(0, 8))

        row2 = tk.Frame(self.card_act, bg=CARD)
        row2.pack(fill='x', pady=(0, 8))
        self.btn_install_svc = tk.Button(
            row2, command=self.run_install_service,
            bg=BG, fg=TEXT, relief='solid', bd=1, pady=7, font=('Segoe UI', 9), cursor='hand2',
        )
        self.btn_install_svc.pack(side='left', fill='x', expand=True, padx=(0, 6))
        self.btn_toggle_tap = tk.Button(
            row2, command=self.run_toggle_tap,
            bg=BG, fg=TEXT, relief='solid', bd=1, pady=7, font=('Segoe UI', 9), cursor='hand2',
        )
        self.btn_toggle_tap.pack(side='left', fill='x', expand=True, padx=(6, 0))

        self.btn_where = tk.Button(
            self.card_act, command=self.show_where_info,
            bg=BG, fg=PRIMARY, relief='flat', pady=7, font=('Segoe UI', 9), cursor='hand2',
        )
        self.btn_where.pack(fill='x', pady=(0, 10))

        self.lbl_tip = tk.Label(
            self.card_act, font=('Segoe UI', 9), fg=MUTED, bg=CARD,
            justify='left', anchor='w', wraplength=670,
        )
        self.lbl_tip.pack(fill='x', pady=(4, 0))

    def _apply_lang(self):
        self.root.title(self.t('window_title') + '  v' + self.release_ver)
        self.lbl_title.configure(text=self.t('window_title'))
        self.lbl_sub.configure(text=self.t('subtitle') + '  ·  v' + self.release_ver + ' / BAR ' + self.project['mobile_version'])
        self.btn_octo.configure(text=self.t('octolab_btn'))
        self.btn_lang.configure(text=self.t('lang_btn'))
        self.lbl_conn_hdr.configure(text=self.t('conn_card'))
        self.btn_check.configure(text=self.t('check_btn'))
        self.btn_ssh.configure(text=self.t('choose_ssh_btn'))
        self.lbl_act_hdr.configure(text=self.t('action_card'))
        self.btn_install_all.configure(text=self.t('install_all_btn'))
        self.btn_install_svc.configure(text=self.t('install_svc_btn'))
        self.btn_where.configure(text=self.t('where_btn'))
        self.lbl_tip.configure(text=self.t('tip_sachesi'))
        self._refresh_status_text()

    def _refresh_status_text(self):
        tap_on = bool(self.last_status and self.last_status.get('volte_tap_configured'))
        self.btn_toggle_tap.configure(text=self.t('toggle_tap_off' if tap_on else 'toggle_tap_on'))
        if not self.last_status:
            self.lbl_status.configure(text=self.t('not_checked'), fg=MUTED)
            return
        st = self.last_status
        app = st.get('mobile_app') or {}
        variant = app.get('variant', 'BB10')
        os_ver = app.get('os_version', '10.3.3')
        app_state = app.get('state', 'unknown')
        rec_count = len(st.get('recordings') or [])
        svc_alive = st.get('daemon_alive')
        engine = 'VoLTE Digital + QSA' if st.get('volte_tap_configured') else 'QSA 16kHz (+18 dB)'
        if self.lang == 'zh':
            svc_txt = ('运行中 (PID ' + str(st.get('daemon_pid')) + ')') if svc_alive else ('已安装但未运行' if st.get('installed') else '未安装')
            app_txt = ('已安装 v' + str(app.get('version', ''))) if app_state == 'installed' else ('未安装' if app_state == 'absent' else app_state)
            lines = [
                '已连接设备：' + str(variant) + '（OS ' + str(os_ver) + '）  ·  剩余空间：' + str(st.get('free_mb', '?')) + ' MB',
                '桌面图标 App：' + app_txt + '  ·  后台自动录音服务：' + svc_txt,
                '音频引擎：' + engine + '  ·  本机已有录音：' + str(rec_count) + ' 条（' + str(st.get('output_folder', '')) + '）',
            ]
        else:
            svc_txt = ('Running (PID ' + str(st.get('daemon_pid')) + ')') if svc_alive else ('Stopped' if st.get('installed') else 'Not installed')
            app_txt = ('Installed v' + str(app.get('version', ''))) if app_state == 'installed' else app_state
            lines = [
                'Connected Phone: ' + str(variant) + ' (OS ' + str(os_ver) + ')  ·  Free Space: ' + str(st.get('free_mb', '?')) + ' MB',
                'Home-Screen App: ' + app_txt + '  ·  Background Daemon: ' + svc_txt,
                'Audio Source: ' + engine + '  ·  Saved Recordings: ' + str(rec_count) + ' (' + str(st.get('output_folder', '')) + ')',
            ]
        self.lbl_status.configure(text='\n'.join(lines), fg=TEXT)

    def _set_busy(self, flag, msg=''):
        self.busy = flag
        state = 'disabled' if flag else 'normal'
        has_bar = (self.res_root / BUNDLED_BAR_REL).is_file()
        self.btn_check.configure(state=state)
        self.btn_ssh.configure(state=state)
        self.btn_install_all.configure(state=('normal' if (not flag and has_bar) else 'disabled'))
        self.btn_install_svc.configure(state=state)
        self.btn_toggle_tap.configure(state=state)
        if flag and msg:
            self.lbl_status.configure(text=msg, fg=PRIMARY)

    def toggle_language(self):
        self.lang = 'en' if self.lang == 'zh' else 'zh'
        self._apply_lang()

    def choose_ssh_config(self):
        chosen = filedialog.askopenfilename(title='Select paired BB10 ssh_config')
        if chosen:
            self.custom_ssh = chosen
            self.check_phone()

    def _start_task(self, busy_msg, fn, done_notice_key=''):
        if self.busy:
            return
        self._set_busy(True, busy_msg)

        def worker():
            try:
                data = fn()
                self.queue.put(('ok', data, done_notice_key))
            except Exception as exc:
                self.queue.put(('err', str(exc), ''))

        threading.Thread(target=worker, daemon=True).start()

    def _poll_queue(self):
        try:
            while True:
                kind, payload, notice_key = self.queue.get_nowait()
                self._set_busy(False)
                if kind == 'ok':
                    self.last_status = payload
                    self._refresh_status_text()
                    if notice_key:
                        messagebox.showinfo(self.t('window_title'), self.t(notice_key))
                else:
                    msg = self.t('err_no_ssh') if 'no_paired_ssh_config' in payload else (self.t('err_prefix') + payload)
                    self.lbl_status.configure(text=msg, fg=WARN)
        except queue.Empty:
            pass
        self.root.after(50, self._poll_queue)

    def check_phone(self):
        self._start_task(self.t('checking'), lambda: inspect_full_phone(custom_config=self.custom_ssh))

    def run_install_all(self):
        self._start_task(self.t('installing_all'), lambda: install_all(custom_config=self.custom_ssh), 'ok_installed_all')

    def run_install_service(self):
        def task():
            stage_and_run('install', custom_config=self.custom_ssh)
            stage_and_run('set-config', {'consent_acknowledged': True, 'enabled': True, 'trigger_mode': 'auto'},
                          custom_config=self.custom_ssh)
            return inspect_full_phone(custom_config=self.custom_ssh)

        self._start_task(self.t('installing_svc'), task, 'ok_installed_svc')

    def run_toggle_tap(self):
        target = not bool(self.last_status and self.last_status.get('volte_tap_configured'))

        def task():
            stage_and_run('set-volte-tap', {'enabled': target}, custom_config=self.custom_ssh)
            return inspect_full_phone(custom_config=self.custom_ssh)

        self._start_task(self.t('toggling_tap'), task)

    def show_where_info(self):
        messagebox.showinfo(self.t('where_title'), self.t('where_body'))

    def open_support_dialog(self):
        win = tk.Toplevel(self.root)
        win.title(self.t('support_title'))
        win.configure(bg=BG)
        win.geometry('540x610')
        win.transient(self.root)

        wrap = tk.Frame(win, bg=BG, padx=24, pady=20)
        wrap.pack(fill='both', expand=True)

        hdr = tk.Frame(wrap, bg=BG)
        hdr.pack(fill='x')
        fav = self._load_image('assets/support/octoooo-favicon.png')
        if fav is not None:
            lbl_icon = tk.Label(hdr, image=fav, bg=BG)
            lbl_icon.pack(side='left', padx=(0, 10))
        tk.Label(hdr, text=self.t('support_heading'), font=('Segoe UI', 14, 'bold'), fg=PRIMARY, bg=BG).pack(side='left')

        tk.Label(
            wrap, text=self.t('support_story'), font=('Segoe UI', 9),
            fg=MUTED, bg=BG, justify='left', anchor='w', wraplength=480,
        ).pack(fill='x', pady=(10, 12))

        links = tk.Frame(wrap, bg=BG)
        links.pack(fill='x', pady=(0, 14))
        for label_key, url in (
            ('support_star', 'https://github.com/Octo-o-o-o/bb10-call-recorder'),
            ('support_studio', 'https://octoooo.com/'),
            ('support_volte', 'https://bb10-volte.octoooo.com/'),
        ):
            tk.Button(
                links, text=self.t(label_key),
                command=lambda u=url: webbrowser.open(u),
                bg=CARD, fg=PRIMARY, relief='solid', bd=1, padx=10, pady=5,
                font=('Segoe UI', 9, 'bold'), cursor='hand2',
            ).pack(side='left', padx=(0, 8))

        qr_card = tk.Frame(wrap, bg=CARD, highlightbackground=BORDER, highlightthickness=1, padx=16, pady=14)
        qr_card.pack(fill='both', expand=True)
        tk.Label(qr_card, text=self.t('support_coffee'), font=('Segoe UI', 10, 'bold'), fg=PRIMARY, bg=CARD).pack(anchor='w')

        provider_var = tk.StringVar(value='alipay')
        amount_var = tk.StringVar(value='custom')

        sel_row = tk.Frame(qr_card, bg=CARD)
        sel_row.pack(fill='x', pady=(8, 6))
        tk.Radiobutton(sel_row, text=self.t('support_alipay'), variable=provider_var, value='alipay', bg=CARD).pack(side='left')
        tk.Radiobutton(sel_row, text=self.t('support_wechat'), variable=provider_var, value='wechat', bg=CARD).pack(side='left', padx=(12, 0))

        amt_row = tk.Frame(qr_card, bg=CARD)
        amt_row.pack(fill='x', pady=(0, 8))
        for val, text in (('custom', self.t('support_custom')), ('9_90', '¥9.90'), ('19_90', '¥19.90'), ('29_90', '¥29.90')):
            tk.Radiobutton(amt_row, text=text, variable=amount_var, value=val, bg=CARD).pack(side='left', padx=(0, 10))

        qr_label = tk.Label(qr_card, bg=CARD)
        qr_label.pack(pady=6)

        def update_qr(*_args):
            rel = 'assets/support/' + provider_var.get() + '-' + amount_var.get() + '.png'
            img = self._load_image(rel)
            if img is not None:
                qr_label.configure(image=img, text='')
            else:
                qr_label.configure(image='', text=rel)

        provider_var.trace_add('write', update_qr)
        amount_var.trace_add('write', update_qr)
        update_qr()

        tk.Label(
            wrap, text=self.t('support_note'), font=('Segoe UI', 8),
            fg=MUTED, bg=BG, justify='left', anchor='w', wraplength=480,
        ).pack(fill='x', pady=(10, 0))


def run_self_test():
    win = tk.Tk()
    win.withdraw()
    app = RecorderDesktopApp(win)
    t0 = time.perf_counter()
    win.update_idletasks()
    app.toggle_language()
    app.toggle_language()
    win.update_idletasks()
    elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 3)
    fav = (resource_root() / 'assets/support/octoooo-favicon.png').is_file()
    win.destroy()
    return {'self_test': 'ok', 'ui_update_ms': elapsed_ms, 'support_assets_present': fav}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--self-test', action='store_true', help='Verify GUI initialization and bundled assets')
    args = parser.parse_args(argv)
    if args.self_test:
        print(json.dumps(run_self_test()))
        return 0
    win = tk.Tk()
    RecorderDesktopApp(win)
    win.mainloop()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
