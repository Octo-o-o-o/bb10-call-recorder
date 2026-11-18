#include "supportcontroller.h"
#include <bb/system/Clipboard>
#include <bb/system/InvokeRequest>
#include <bb/system/InvokeTargetReply>
#include <bb/system/InvokeReplyError>
#include <QUrl>

SupportController::SupportController(QObject *parent)
    : QObject(parent), m_invoker(this), m_reply(0), m_opening(false)
{
    m_timer.setSingleShot(true);
    connect(&m_timer, SIGNAL(timeout()), this, SLOT(timedOut()));
}

void SupportController::reset()
{
    if (m_opening) return;
    m_message.clear();
    m_link.clear();
    emit changed();
}

void SupportController::openLink(const QString &id)
{
    if (m_opening) return;
    QString url;
    if (id == "github") url = "https://github.com/Octo-o-o-o/bb10-call-recorder";
    else if (id == "studio") url = "https://octoooo.com/";
    else if (id == "volte") url = "https://bb10-volte.octoooo.com/";
    if (url.isEmpty()) return;
    m_link = url;
    m_message = "support_opening";
    bb::system::InvokeRequest request;
    request.setTarget("sys.browser");
    request.setAction("bb.action.OPEN");
    request.setUri(QUrl(url));
    bb::system::InvokeTargetReply *reply = m_invoker.invoke(request);
    m_reply = reply;
    m_opening = reply != 0;
    if (reply) {
        connect(reply, SIGNAL(finished()), this, SLOT(finished()));
        m_timer.start(10000);
    } else {
        m_message = "support_open_failed";
    }
    emit changed();
}

void SupportController::finished()
{
    bb::system::InvokeTargetReply *reply = qobject_cast<bb::system::InvokeTargetReply *>(sender());
    if (!reply || reply != m_reply) return;
    m_timer.stop();
    m_message = reply->error() == bb::system::InvokeReplyError::None ? "support_opened" : "support_open_failed";
    m_opening = false;
    m_reply = 0;
    reply->deleteLater();
    emit changed();
}

void SupportController::timedOut()
{
    if (m_reply) {
        disconnect(m_reply, 0, this, 0);
        m_reply->deleteLater();
        m_reply = 0;
    }
    m_opening = false;
    m_message = "support_open_failed";
    emit changed();
}

void SupportController::copyLink()
{
    if (m_link.isEmpty()) return;
    bb::system::Clipboard clipboard;
    m_message = clipboard.insert("text/plain", m_link.toUtf8()) ? "support_copied" : "support_copy_failed";
    emit changed();
}
