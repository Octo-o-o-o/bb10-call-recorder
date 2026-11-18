#ifndef BB10_RECORDER_CONTROLLER_H
#define BB10_RECORDER_CONTROLLER_H

#include <QObject>
#include <QProcess>
#include <QTimer>
#include <QVariantList>
#include <QVariantMap>

class RecorderController : public QObject {
    Q_OBJECT
    Q_PROPERTY(QString language READ language WRITE setLanguage NOTIFY languageChanged)
    Q_PROPERTY(QString statusTitle READ statusTitle NOTIFY stateChanged)
    Q_PROPERTY(QString statusDetail READ statusDetail NOTIFY stateChanged)
    Q_PROPERTY(QString engineText READ engineText NOTIFY stateChanged)
    Q_PROPERTY(QString folderText READ folderText NOTIFY stateChanged)
    Q_PROPERTY(QString notice READ notice NOTIFY stateChanged)
    Q_PROPERTY(bool busy READ busy NOTIFY stateChanged)
    Q_PROPERTY(bool installed READ installed NOTIFY stateChanged)
    Q_PROPERTY(bool recordingActive READ recordingActive NOTIFY stateChanged)
    Q_PROPERTY(bool callEligible READ callEligible NOTIFY stateChanged)
    Q_PROPERTY(bool consentAcknowledged READ consentAcknowledged NOTIFY stateChanged)
    Q_PROPERTY(bool autoRecord READ autoRecord NOTIFY stateChanged)
    Q_PROPERTY(bool includeNumber READ includeNumber NOTIFY stateChanged)
    Q_PROPERTY(bool sdAvailable READ sdAvailable NOTIFY stateChanged)
    Q_PROPERTY(bool volteInstalled READ volteInstalled NOTIFY stateChanged)
    Q_PROPERTY(bool volteTapConfigured READ volteTapConfigured NOTIFY stateChanged)
    Q_PROPERTY(QString version READ version CONSTANT)
    Q_PROPERTY(QString storageLocation READ storageLocation NOTIFY stateChanged)
    Q_PROPERTY(QVariantList recordings READ recordings NOTIFY stateChanged)

public:
    explicit RecorderController(QObject *parent = 0);

    QString language() const { return m_language; }
    void setLanguage(const QString &lang);

    QString statusTitle() const;
    QString statusDetail() const;
    QString engineText() const;
    QString folderText() const;
    QString notice() const { return m_notice; }

    bool busy() const { return m_busy; }
    bool installed() const { return m_state.value("installed").toBool(); }
    bool recordingActive() const { return m_state.value("recording_active").toBool(); }
    bool callEligible() const { return m_state.value("call_eligible").toBool(); }
    bool consentAcknowledged() const;
    bool autoRecord() const;
    bool includeNumber() const;
    bool sdAvailable() const { return m_state.value("sd_available").toBool(); }
    bool volteInstalled() const { return m_state.value("volte_installed").toBool(); }
    bool volteTapConfigured() const { return m_state.value("volte_tap_configured").toBool(); }
    QString version() const { return QString::fromLatin1(BB10_RECORDER_VERSION_STR); }
    QString storageLocation() const;
    QVariantList recordings() const { return m_recordings; }

    Q_INVOKABLE QString label(const QString &key) const;
    Q_INVOKABLE void refresh();
    Q_INVOKABLE void installService();
    Q_INVOKABLE void acknowledgeConsent();
    Q_INVOKABLE void startManual();
    Q_INVOKABLE void stopManual();
    Q_INVOKABLE void setAutoRecord(bool enabled);
    Q_INVOKABLE void setStorageLocation(const QString &location);
    Q_INVOKABLE void setIncludeNumber(bool include);
    Q_INVOKABLE void setVolteTap(bool enabled);
    Q_INVOKABLE void deleteRecording(const QString &recId);
    Q_INVOKABLE void uninstallService();

signals:
    void stateChanged();
    void languageChanged();

private slots:
    void onProcessStarted();
    void onProcessOutput();
    void onProcessFinished(int exitCode, QProcess::ExitStatus exitStatus);
    void onProcessError(QProcess::ProcessError error);
    void onTimeout();

private:
    void runRootAction(const QString &action, const QVariantMap &payload = QVariantMap());

    QProcess m_process;
    QTimer m_timer;
    QByteArray m_pendingInput;
    QByteArray m_output;
    QVariantMap m_state;
    QVariantList m_recordings;
    QString m_language;
    QString m_notice;
    bool m_busy;
};

#endif
