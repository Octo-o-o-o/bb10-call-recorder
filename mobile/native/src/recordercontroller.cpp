#include "recordercontroller.h"
#include "ui_strings.h"
#include <bb/data/JsonDataAccess>
#include <QCoreApplication>
#include <QDir>
#include <QFileInfo>

RecorderController::RecorderController(QObject *parent)
    : QObject(parent), m_language("zh"), m_busy(false) {
    m_timer.setSingleShot(true);
    connect(&m_process, SIGNAL(started()), this, SLOT(onProcessStarted()));
    connect(&m_process, SIGNAL(readyReadStandardOutput()), this, SLOT(onProcessOutput()));
    connect(&m_process, SIGNAL(finished(int,QProcess::ExitStatus)),
            this, SLOT(onProcessFinished(int,QProcess::ExitStatus)));
    connect(&m_process, SIGNAL(error(QProcess::ProcessError)),
            this, SLOT(onProcessError(QProcess::ProcessError)));
    connect(&m_timer, SIGNAL(timeout()), this, SLOT(onTimeout()));
}

QString RecorderController::label(const QString &key) const {
    return recorderLabel(m_language, key);
}

void RecorderController::setLanguage(const QString &lang) {
    if (lang != "zh" && lang != "en") return;
    if (m_language == lang) return;
    m_language = lang;
    emit languageChanged();
    emit stateChanged();
    if (installed() && !m_busy) {
        QVariantMap payload;
        payload.insert("language", lang);
        runRootAction("set-config", payload);
    }
}

bool RecorderController::consentAcknowledged() const {
    return m_state.value("config").toMap().value("consent_acknowledged").toBool();
}

bool RecorderController::autoRecord() const {
    QVariantMap cfg = m_state.value("config").toMap();
    return cfg.value("enabled", true).toBool() && cfg.value("trigger_mode", "auto").toString() == "auto";
}

bool RecorderController::includeNumber() const {
    return m_state.value("config").toMap().value("include_number").toBool();
}

QString RecorderController::storageLocation() const {
    return m_state.value("config").toMap().value("storage_location", "internal").toString();
}

QString RecorderController::statusTitle() const {
    if (!installed()) return label("status_uninstalled");
    if (recordingActive()) return label("status_recording");
    QVariantMap cfg = m_state.value("config").toMap();
    if (!cfg.value("enabled", true).toBool()) return label("status_disabled");
    return autoRecord() ? label("status_ready_auto") : label("status_ready_manual");
}

QString RecorderController::statusDetail() const {
    const int freeMb = m_state.value("free_mb").toInt();
    const QString callState = m_state.value("call_state", "idle").toString();
    if (m_language == "en") {
        return QString("Call state: %1  ·  Free space: %2 MB").arg(callState).arg(freeMb);
    }
    return QString::fromUtf8("当前状态：%1  ·  可用空间：%2 MB").arg(callState).arg(freeMb);
}

QString RecorderController::engineText() const {
    return volteTapConfigured() ? label("volte_tap_on") : label("volte_tap_off");
}

QString RecorderController::folderText() const {
    return m_state.value("output_folder", "/accounts/1000/shared/voice/bb10-call-recorder").toString();
}

void RecorderController::refresh() { runRootAction("status"); }
void RecorderController::installService() { runRootAction("install"); }

void RecorderController::acknowledgeConsent() {
    QVariantMap payload;
    payload.insert("consent_acknowledged", true);
    payload.insert("enabled", true);
    runRootAction("set-config", payload);
}

void RecorderController::startManual() { runRootAction("start-manual"); }
void RecorderController::stopManual() { runRootAction("stop-manual"); }

void RecorderController::setAutoRecord(bool enabled) {
    QVariantMap payload;
    payload.insert("enabled", true);
    payload.insert("trigger_mode", enabled ? "auto" : "manual");
    runRootAction("set-config", payload);
}

void RecorderController::setStorageLocation(const QString &location) {
    QVariantMap payload;
    payload.insert("storage_location", location == "sdcard" ? "sdcard" : "internal");
    runRootAction("set-config", payload);
}

void RecorderController::setIncludeNumber(bool include) {
    QVariantMap payload;
    payload.insert("include_number", include);
    runRootAction("set-config", payload);
}

void RecorderController::setVolteTap(bool enabled) {
    QVariantMap payload;
    payload.insert("enabled", enabled);
    runRootAction("set-volte-tap", payload);
}

void RecorderController::deleteRecording(const QString &recId) {
    QVariantMap payload;
    payload.insert("id", recId);
    runRootAction("delete-recording", payload);
}

void RecorderController::uninstallService() {
    runRootAction("uninstall");
}

void RecorderController::runRootAction(const QString &action, const QVariantMap &payload) {
    if (m_busy) return;
    if (!QFileInfo("/bin/__root").isExecutable()) {
        m_notice = (m_language == "en") ? "Root helper /bin/__root not found." : QString::fromUtf8("未检测到 Root 权限入口 /bin/__root。");
        emit stateChanged();
        return;
    }
    QString runtimeRoot = QDir::current().absoluteFilePath("app/native/assets/runtime");
    if (!QFileInfo(runtimeRoot + "/runtime/entry.py").isFile()) {
        runtimeRoot = QDir::cleanPath(QCoreApplication::applicationDirPath() + "/assets/runtime");
    }
    if (!QFileInfo(runtimeRoot + "/runtime/entry.py").isFile()) {
        m_notice = (m_language == "en") ? "Bundled runtime scripts missing." : QString::fromUtf8("未找到内置后台运行脚本。");
        emit stateChanged();
        return;
    }
    QByteArray encodedPayload;
    if (!payload.isEmpty()) {
        bb::data::JsonDataAccess jda;
        QByteArray jsonBytes;
        jda.saveToBuffer(payload, &jsonBytes);
        encodedPayload = jsonBytes.toBase64();
    }
    QString safeRoot = runtimeRoot;
    safeRoot.replace("'", "'\\''");
    QString cmd =
        "unset PYTHONOPTIMIZE PYTHONINSPECT PYTHONSTARTUP PYTHONUSERBASE PYTHONPATH PYTHONHOME LD_PRELOAD ENV BASH_ENV\n"
        "export PATH=/proc/boot:/bin:/usr/bin:/base/bin:/base/usr/bin\n"
        "export LD_LIBRARY_PATH=/base/usr/lib:/base/lib:/base/lib/dll:/radio/lib:/radio/lib/dll:/radio/usr/lib:/proc/boot\n"
        "export PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 PYTHONHOME=/usr PYTHONPATH=/usr/lib/python32.zip:/usr/lib/python3.2/lib-dynload\n"
        "umask 077\n"
        "STAGE=\"/var/bb10_rec_ui_$$\"\n"
        "rm -rf \"$STAGE\"\n"
        "mkdir -m 700 \"$STAGE\" || exit 73\n"
        "trap 'rm -rf \"$STAGE\"' 0\n"
        "cp -R '" + safeRoot + "/device' '" + safeRoot + "/runtime' \"$STAGE/\" || exit 74\n"
        "chmod 700 \"$STAGE/device\" \"$STAGE/runtime\"\n"
        "for f in \"$STAGE\"/device/*.py \"$STAGE\"/runtime/*.py; do\n"
        "  chmod 600 \"$f\" && /proc/boot/pathtrust \"!$f\" || exit 75\n"
        "done\n"
        "for f in \"$STAGE\"/device/*.sh; do\n"
        "  if [ -f \"$f\" ]; then chmod 700 \"$f\" && /proc/boot/pathtrust \"!$f\" || exit 76; fi\n"
        "done\n"
        "/usr/bin/python3.2 -B \"$STAGE/runtime/entry.py\" " + action;
    if (!encodedPayload.isEmpty()) {
        cmd += " '" + QString::fromLatin1(encodedPayload) + "'";
    }
    cmd += "\nexit $?\n";

    m_pendingInput = cmd.toUtf8();
    m_output.clear();
    m_notice.clear();
    m_busy = true;
    m_process.setProcessChannelMode(QProcess::MergedChannels);
    m_timer.start(30000);
    m_process.start("/bin/__root", QStringList(), QIODevice::ReadWrite);
    emit stateChanged();
}

void RecorderController::onProcessStarted() {
    m_process.write(m_pendingInput);
    m_process.closeWriteChannel();
    m_pendingInput.clear();
}

void RecorderController::onProcessOutput() {
    m_output += m_process.readAllStandardOutput();
    if (m_output.size() > 262144) {
        m_process.kill();
    }
}

void RecorderController::onProcessFinished(int exitCode, QProcess::ExitStatus exitStatus) {
    onProcessOutput();
    m_timer.stop();
    m_busy = false;
    if (exitCode == 0 && exitStatus == QProcess::NormalExit) {
        const QList<QByteArray> lines = m_output.split('\n');
        for (int i = lines.size() - 1; i >= 0; --i) {
            const QByteArray trimmed = lines.at(i).trimmed();
            if (!trimmed.startsWith('{')) continue;
            bb::data::JsonDataAccess jda;
            QVariantMap parsed = jda.loadFromBuffer(trimmed).toMap();
            if (!jda.hasError() && parsed.value("ok").toBool()) {
                m_state = parsed.value("data").toMap();
                m_recordings = m_state.value("recordings").toList();
                const QString savedLang = m_state.value("config").toMap().value("language").toString();
                if ((savedLang == "zh" || savedLang == "en") && savedLang != m_language) {
                    m_language = savedLang;
                    emit languageChanged();
                }
                break;
            } else if (!jda.hasError() && !parsed.value("error").toString().isEmpty()) {
                m_notice = parsed.value("error").toString();
            }
        }
    } else if (m_notice.isEmpty()) {
        m_notice = QString::fromUtf8(m_output.trimmed().left(200));
    }
    m_output.clear();
    emit stateChanged();
}

void RecorderController::onProcessError(QProcess::ProcessError error) {
    if (error != QProcess::FailedToStart) return;
    m_timer.stop();
    m_busy = false;
    m_pendingInput.clear();
    m_notice = (m_language == "en") ? "Failed to start /bin/__root." : QString::fromUtf8("无法启动 Root 管理桥接。");
    emit stateChanged();
}

void RecorderController::onTimeout() {
    m_notice = (m_language == "en") ? "Operation timed out." : QString::fromUtf8("后台响应超时。");
    m_process.kill();
}
