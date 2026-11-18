cmake_minimum_required(VERSION 3.20)
project(bb10_call_recorder LANGUAGES CXX)

set(CMAKE_RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/arm/o.le-v7-g")
set(BB10_RECORDER_VERSION "0.1.0.1" CACHE STRING "Mobile release version")

include(BB10Qt4)
qt4_wrap_cpp(MOC_SOURCES src/recordercontroller.h src/supportcontroller.h)
add_executable(bb10recorder src/main.cpp src/recordercontroller.cpp src/supportcontroller.cpp ${MOC_SOURCES})
target_include_directories(bb10recorder PRIVATE src)
target_compile_definitions(bb10recorder PRIVATE BB10_RECORDER_VERSION_STR="${BB10_RECORDER_VERSION}")
target_link_libraries(bb10recorder PRIVATE
    bbcascades bbdata bbsystem bbmultimedia
    QtDeclarative QtScript QtSvg QtSql sqlite3 z QtXmlPatterns
    QtGui QtNetwork socket QtCore crypto)
