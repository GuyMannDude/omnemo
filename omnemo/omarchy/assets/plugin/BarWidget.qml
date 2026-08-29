import QtQuick
import Quickshell
import Quickshell.Io
import qs.Commons
import qs.Ui

// Omnemo bar widget: memory count and what the machine learned today,
// read from `omnemo stats --json` once a minute (and on click).
//
// Degrades honestly: if the CLI is missing or errors, the widget shows
// "mem ?" rather than a stale or invented number.
BarWidget {
  id: root
  moduleName: "omnemo.memory"

  property int memoryCount: -1
  property int learnedToday: 0

  readonly property string displayText: memoryCount < 0
    ? "𝍇 ?"
    : (learnedToday > 0
        ? "𝍇 " + memoryCount + " +" + learnedToday
        : "𝍇 " + memoryCount)

  readonly property int refreshIntervalSec: 60

  function refresh() {
    if (!statsProcess.running) statsProcess.running = true
  }

  function applyStats(text) {
    try {
      var s = JSON.parse(text)
      root.memoryCount = s.memory_count
      root.learnedToday = s.learned_today
    } catch (e) {
      root.memoryCount = -1
    }
  }

  implicitWidth: button.implicitWidth
  implicitHeight: button.implicitHeight

  Process {
    id: statsProcess
    command: ["omnemo", "stats", "--json"]
    stdout: StdioCollector {
      onStreamFinished: root.applyStats(text)
    }
    onExited: function(exitCode) {
      if (exitCode !== 0) root.memoryCount = -1
    }
  }

  Timer {
    interval: root.refreshIntervalSec * 1000
    running: true
    repeat: true
    triggeredOnStart: true
    onTriggered: root.refresh()
  }

  WidgetButton {
    id: button
    anchors.fill: parent
    bar: root.bar
    text: root.vertical ? "𝍇" : root.displayText
    labelVisible: true
    hasVisualContent: text !== ""
    horizontalMargin: 8.75
    verticalPadding: 8.75

    onPressed: function(b) {
      root.refresh()
    }
  }
}
