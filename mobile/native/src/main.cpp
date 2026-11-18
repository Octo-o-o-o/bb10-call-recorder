#include "recordercontroller.h"
#include "supportcontroller.h"
#include <bb/cascades/Application>
#include <bb/cascades/QmlDocument>
#include <bb/cascades/AbstractPane>

using namespace bb::cascades;

int main(int argc, char **argv) {
    Application app(argc, argv);
    RecorderController controller;
    SupportController support;
    QmlDocument *qml = QmlDocument::create("asset:///main.qml").parent(&app);
    qml->setContextProperty("recorderController", &controller);
    qml->setContextProperty("supportController", &support);
    AbstractPane *root = qml->createRootObject<AbstractPane>();
    Application::instance()->setScene(root);
    controller.refresh();
    return Application::exec();
}
