import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtMultimedia

ApplicationWindow {
    id: root
    width: 1240; height: 800
    minimumWidth: 980; minimumHeight: 660
    visible: true
    color: "#080808"
    title: s.fileName || "Плеер"
    font.family: "Onest"
    font.pixelSize: 13
    palette.window: "#101010"
    palette.windowText: "#eeeef0"
    palette.base: "#181818"
    palette.text: "#eeeef0"
    palette.button: "#181818"
    palette.buttonText: "#eeeef0"
    palette.highlight: "#5b526f"
    palette.highlightedText: "#ffffff"
    property var s: bridge.state
    property bool trimOpen: false
    property bool semantic: false
    property bool followText: true
    property bool videoOnly: false
    property bool previewing: false
    property int lastActiveRow: -1
    readonly property bool hasQuery: !semantic && search.text.trim().length > 0
    readonly property bool resultsCurrent: s.searchQuery === search.text.trim() && s.searchPerformed
    readonly property bool playbackKeysAllowed: !s.onboarding && !s.settingsOpen && !meaning.settingsVisible && !volumePopup.visible && !speedMenu.visible && !transcriptMenu.visible && !trimStart.popupVisible && !trimEnd.popupVisible &&
        !activeFocusControl && !(activeFocusItem instanceof TextInput) && !(activeFocusItem instanceof TextEdit)
    property real clipStart: 0
    property real clipEnd: 60
    property real zoomFactor: 2
    readonly property real total: player.duration/1000
    readonly property real clipLength: Math.max(0,clipEnd-clipStart)
    readonly property real viewSpan: Math.min(total,Math.max(15,clipLength*zoomFactor))
    readonly property real viewStart: Math.max(0, Math.min(total-viewSpan,(clipStart+clipEnd-viewSpan)/2))

    function setClip(start,end) {
        clipStart=Math.max(0,Math.min(total-.1,start))
        clipEnd=Math.max(clipStart+.1,Math.min(total,end))
    }
    function togglePlayback() {
        if (!s.hasMedia) return
        player.playbackState===MediaPlayer.PlayingState ? player.pause() : player.play()
    }
    function toggleFullScreen() {
        if (videoOnly) { videoOnly=false; root.showNormal() }
        else { videoOnly=true;root.showFullScreen() }
    }
    function openTrim() {
        if (s.selectedStart >= 0) bridge.trimSelection()
        else { setClip(player.position/1000,Math.min(total,player.position/1000+30));trimOpen=true }
    }
    function closeTrim() {
        if(previewing){player.pause();previewing=false}
        trimOpen=false
    }
    function acceptSearch(backward) {
        if (root.resultsCurrent && s.searchCount>0) bridge.navigateHit(backward ? -1 : 1)
        else bridge.findText(search.text)
    }
    function selectSection(useMeaning) {
        root.semantic = useMeaning
        bridge.setSearchSection(useMeaning)
        if (!useMeaning && s.selectedStart >= 0)
            Qt.callLater(() => transcript.positionViewAtIndex(s.selectedStart, ListView.Contain))
    }
    function focusTextSearch() { root.selectSection(false); search.forceActiveFocus() }
    function navigateSearch(direction) {
        if (root.semantic) bridge.navigateMeaning(direction)
        else bridge.navigateHit(direction)
    }
    Shortcut { sequence: "Ctrl+O"; enabled:!s.onboarding&&!s.settingsOpen; onActivated: bridge.openDialog() }
    Shortcut { sequence: "Meta+O"; enabled:!s.onboarding&&!s.settingsOpen; onActivated: bridge.openDialog() }
    Shortcut { sequence: "Space"; enabled: root.playbackKeysAllowed; onActivated: root.togglePlayback() }
    Shortcut { sequence: "Ctrl+F"; enabled:!s.onboarding&&!s.settingsOpen; onActivated: root.focusTextSearch() }
    Shortcut { sequence: "Meta+F"; enabled:!s.onboarding&&!s.settingsOpen; onActivated: root.focusTextSearch() }
    Shortcut { sequence: "Ctrl+Return"; enabled:root.semantic && !s.settingsOpen && !s.onboarding && !meaning.settingsVisible; onActivated:meaning.launch() }
    Shortcut { sequence: "Meta+Return"; enabled:root.semantic && !s.settingsOpen && !s.onboarding && !meaning.settingsVisible; onActivated:meaning.launch() }
    Shortcut { sequence: "Ctrl+G"; enabled:root.hasQuery; onActivated:bridge.navigateHit(1) }
    Shortcut { sequence: "Meta+G"; enabled:root.hasQuery; onActivated:bridge.navigateHit(1) }
    Shortcut { sequence: "F3"; enabled:root.hasQuery || (root.semantic && s.meaningCount>0); onActivated:root.navigateSearch(1) }
    Shortcut { sequence: "Shift+F3"; enabled:root.hasQuery || (root.semantic && s.meaningCount>0); onActivated:root.navigateSearch(-1) }
    Shortcut { sequence: "Ctrl+,"; enabled:!s.onboarding; onActivated:bridge.settings() }
    Shortcut { sequence: "Meta+,"; enabled:!s.onboarding; onActivated:bridge.settings() }
    Shortcut { sequence: "Escape"; enabled:!meaning.settingsVisible && !volumePopup.visible && !speedMenu.visible && !transcriptMenu.visible && !trimStart.popupVisible && !trimEnd.popupVisible; onActivated: { if(s.onboarding) {if(s.setupBusy) bridge.cancelSetup();else bridge.finishSetup()} else if (videoOnly) root.toggleFullScreen(); else if(s.settingsOpen) bridge.closeSettings(); else if(s.busy) bridge.cancelOperation(); else root.closeTrim() } }
    Shortcut { sequence: "Right"; enabled: root.playbackKeysAllowed; onActivated: player.setPosition(Math.min(player.duration,player.position+5000)) }
    Shortcut { sequence: "Left"; enabled: root.playbackKeysAllowed; onActivated: player.setPosition(Math.max(0,player.position-5000)) }
    Shortcut { sequence: "I"; enabled: root.playbackKeysAllowed && s.hasMedia; onActivated: {setClip(player.position/1000,Math.max(clipEnd,player.position/1000+5));trimOpen=true} }
    Shortcut { sequence: "O"; enabled: root.playbackKeysAllowed && s.hasMedia; onActivated: {setClip(Math.min(clipStart,player.position/1000-1),player.position/1000);trimOpen=true} }

    Connections {
        target: bridge
        function onSeekRequested(milliseconds) { player.setPosition(milliseconds) }
        function onClipRequested(start,end) { root.setClip(start,end);root.trimOpen=true }
        function onRowRevealRequested(index) { if(!root.semantic) {transcript.forceLayout();transcript.positionViewAtIndex(index,ListView.Contain)} }
        function onChanged() {
            if (!root.semantic && followText && s.activeRow!==root.lastActiveRow && s.activeRow>=0 && !transcript.moving)
                transcript.positionViewAtIndex(s.activeRow,ListView.Contain)
            root.lastActiveRow=s.activeRow
        }
    }
    Connections {
        target: player
        function onPositionChanged(value) {
            if (root.previewing && value>=root.clipEnd*1000) { player.pause();root.previewing=false }
        }
        function onPlaybackStateChanged() { if(player.playbackState!==MediaPlayer.PlayingState) root.previewing=false }
        function onSourceChanged() {
            root.trimOpen=false;root.previewing=false;root.clipStart=0;root.clipEnd=60
            search.text="";meaning.queryText="";root.selectSection(false);root.contentItem.forceActiveFocus()
        }
        function onDurationChanged(value) { if(value>0) root.clipEnd=Math.min(60,value/1000) }
    }
    DropArea {
        anchors.fill: parent
        onDropped: drop => { if(drop.hasUrls) {bridge.openMedia(drop.urls[0]);drop.acceptProposedAction()} }
    }
    ColumnLayout {
        enabled:!s.onboarding && !s.settingsOpen
        anchors.fill: parent
        spacing: 0
        RowLayout {
            visible: !root.videoOnly
            Layout.fillWidth: true
            Layout.leftMargin: 24; Layout.rightMargin: 24
            Layout.topMargin: 12;Layout.bottomMargin: 12
            spacing: 16
            ColumnLayout {
                spacing: 4;Layout.fillWidth: true
                Text { textFormat: Text.PlainText; text: s.title; color: "#eeeef0"; font.family: "Onest"; font.pixelSize: 18; font.weight: Font.Medium; elide: Text.ElideMiddle; Layout.fillWidth: true }
                Text { textFormat: Text.PlainText;
                    objectName:"mediaMetadata"
                    text: s.hasMedia ? bridge.formatTime(root.total) + " · " + s.fileName.split(".").pop().toUpperCase() + (player.hasVideo ? (s.videoResolution.length ? " · "+s.videoResolution : "") : " · Аудио") : "Видео, звук и текст — рядом"
                    color: "#a1a1aa"; font.family: "Onest"; font.pixelSize: 12
                }
            }
            PButton { text: "Открыть файл"; iconName: "folder-open"; hint: "Открыть видео или аудио"; onClicked: bridge.openDialog() }
        }
        Rectangle {
            visible: s.error.length>0
            Layout.fillWidth: true
            implicitHeight: errorRow.implicitHeight+16
            color: "#281f20"
            RowLayout {
                id: errorRow;anchors.fill: parent;anchors.leftMargin: 24;anchors.rightMargin: 16;anchors.topMargin: 8;anchors.bottomMargin: 8
                Text { textFormat: Text.PlainText; text: s.error; color: "#efc3bc"; font.family: "Onest"; font.pixelSize: 12; wrapMode: Text.WordWrap; Layout.fillWidth: true }
                PButton { iconName: "x"; quiet: true; hint: "Скрыть сообщение"; onClicked: bridge.dismissError() }
            }
        }
        SplitView {
            id: split
            orientation: Qt.Horizontal
            Layout.fillWidth: true;Layout.fillHeight: true
            handle: Rectangle { implicitWidth: root.videoOnly ? 0 : 1; color: "#343438" }
            Item {
                id:mediaPane
                SplitView.preferredWidth: root.width*.62
                SplitView.minimumWidth: 520
                SplitView.fillWidth: true
                ColumnLayout {
                    anchors.fill: parent
                    anchors.leftMargin: root.videoOnly ? 0 : 24
                    anchors.rightMargin: root.videoOnly ? 0 : 24
                    anchors.topMargin: root.videoOnly ? 0 : 16
                    anchors.bottomMargin: 20
                    spacing: 14
                    Rectangle {
                        id: videoFrame
                        Layout.fillWidth: true;Layout.fillHeight: true
                        Layout.minimumHeight: 180
                        color: "#101010";radius: 9;clip: true
                        VideoOutput {
                            id: video;anchors.fill: parent;visible: s.hasMedia && player.hasVideo
                            Component.onCompleted: bridge.attachVideo(video.videoSink)
                            fillMode: VideoOutput.PreserveAspectFit
                            TapHandler { onTapped: {root.contentItem.forceActiveFocus();root.togglePlayback()} onDoubleTapped: root.toggleFullScreen() }
                        }
                        ColumnLayout {
                            visible: s.hasMedia && !player.hasVideo && player.duration>0
                            anchors.centerIn: parent;width: parent.width*.78;spacing: 18
                            Image { source: assetRoot+"icons/audio-lines.svg"; sourceSize: Qt.size(32,32);Layout.alignment: Qt.AlignHCenter;Layout.preferredWidth: 32;Layout.preferredHeight: 32;opacity: .7 }
                            Text { textFormat: Text.PlainText; text:s.title;color:"#eeeef0";font.family:"Onest";font.pixelSize:20;font.weight:Font.Medium;Layout.fillWidth:true;horizontalAlignment:Text.AlignHCenter;wrapMode:Text.WordWrap }
                            Waveform { Layout.fillWidth:true;implicitHeight:110;peaks:bridge.waveform;duration:root.total;position:player.position/1000;viewEnd:root.total;onSeek:seconds=>player.setPosition(seconds*1000) }
                        }
                        Button {
                            id:emptyMedia
                            objectName:"emptyMediaButton"
                            anchors.fill:parent
                            visible: !s.hasMedia
                            padding:0;hoverEnabled:true;focusPolicy:Qt.StrongFocus
                            Accessible.name:"Открыть видео или аудио"
                            Accessible.description:"Выберите файл или перетащите запись в эту область."
                            onClicked:bridge.openDialog()
                            HoverHandler{cursorShape:Qt.PointingHandCursor}
                            background:Rectangle {
                                radius:9;color:emptyMedia.down?"#181818":emptyMedia.hovered?"#131315":"#101010"
                                border.width:emptyMedia.visualFocus?1:0;border.color:"#b9b1f0"
                            }
                            contentItem:Item {
                                ColumnLayout {
                                    anchors.centerIn: parent;width: Math.min(360,parent.width-48);spacing: 18
                                    Image { source:assetRoot+"icons/folder-open.svg";sourceSize:Qt.size(30,30);Layout.preferredWidth:30;Layout.preferredHeight:30;opacity:.6;Layout.alignment:Qt.AlignHCenter }
                                    Text { textFormat: Text.PlainText; text:"Откройте запись";color:"#eeeef0";font.family:"Onest";font.pixelSize:22;font.weight:Font.Medium;Layout.alignment:Qt.AlignHCenter }
                                    Text { textFormat: Text.PlainText; text:"Перетащите видео или аудио сюда\nили выберите файл на устройстве.";color:"#a1a1aa";font.family:"Onest";font.pixelSize:13;lineHeight:1.5;horizontalAlignment:Text.AlignHCenter;Layout.alignment:Qt.AlignHCenter }
                                }
                            }
                        }
                    }
                    Slider {
                        id: seek;Layout.fillWidth:true;implicitHeight:12
                        from:0;to:Math.max(1,player.duration);value:player.position
                        enabled:s.hasMedia && player.seekable
                        onMoved: player.setPosition(value)
                        Accessible.name:"Позиция воспроизведения"
                        background: Rectangle {
                            x:seek.leftPadding;y:seek.topPadding+seek.availableHeight/2-height/2
                            width:seek.availableWidth;height:4;radius:2;color:"#343437"
                            Rectangle { width:seek.visualPosition*parent.width;height:parent.height;radius:2;color:"#b9b1f0" }
                        }
                        handle: Rectangle { x:seek.leftPadding+seek.visualPosition*(seek.availableWidth-width);y:seek.topPadding+seek.availableHeight/2-height/2;width:10;height:10;radius:5;color:seek.pressed?"#ffffff":"#ddd8ee" }
                    }
                    Item {
                        Layout.fillWidth:true;implicitHeight:40
                        Text { textFormat: Text.PlainText; anchors.left:parent.left;anchors.verticalCenter:parent.verticalCenter;text:bridge.formatTime(player.position/1000)+" / "+bridge.formatTime(root.total);color:"#b6b6bd";font.family:"Onest";font.pixelSize:12 }
                        Row {
                            objectName:"transportMain";anchors.centerIn:parent;spacing:mediaPane.width<650?6:10
                            PButton { anchors.verticalCenter:parent.verticalCenter;iconName:"rewind-10";iconSize:22;width:mediaPane.width<650?32:42;hint:"Назад на 10 секунд";quiet:true;enabled:s.hasMedia;onClicked:player.setPosition(Math.max(0,player.position-10000)) }
                            PButton { objectName:"playPause";circular:true;iconName:player.playbackState===MediaPlayer.PlayingState?"pause-filled":"play-filled";hint:player.playbackState===MediaPlayer.PlayingState?"Пауза · Пробел":"Воспроизвести · Пробел";width:44;height:44;iconSize:20;enabled:s.hasMedia;onClicked:root.togglePlayback() }
                            PButton { anchors.verticalCenter:parent.verticalCenter;iconName:"forward-10";iconSize:22;width:mediaPane.width<650?32:42;hint:"Вперёд на 10 секунд";quiet:true;enabled:s.hasMedia;onClicked:player.setPosition(Math.min(player.duration,player.position+10000)) }
                        }
                        Row {
                            objectName:"transportOptions";anchors.right:parent.right;anchors.verticalCenter:parent.verticalCenter;spacing:4
                            PButton {
                                id:volumeButton
                                anchors.verticalCenter:parent.verticalCenter
                                width:mediaPane.width<650?32:36
                                iconName:sound.muted?"volume-x":"volume-2";quiet:true;hint:"Громкость"
                                onClicked:volumePopup.open()
                                Popup {
                                    id:volumePopup;objectName:"volumePopup"
                                    x:parent.width-width;y:-height-10;width:204;height:112;padding:14
                                    focus:true;closePolicy:Popup.CloseOnEscape|Popup.CloseOnPressOutside
                                    background:Rectangle{color:"#181818";radius:14;border.color:"#38383b"}
                                    onOpened:volumeSlider.forceActiveFocus()
                                    ColumnLayout{
                                        anchors.fill:parent;spacing:8
                                        RowLayout{
                                            Layout.fillWidth:true
                                            Text{ textFormat: Text.PlainText;text:"Громкость";color:"#eeeef0";font.family:"Onest";font.pixelSize:12;Layout.fillWidth:true}
                                            PButton{iconName:sound.muted?"volume-x":"volume-2";quiet:true;implicitHeight:26;implicitWidth:26;hint:sound.muted?"Включить звук":"Выключить звук";onClicked:sound.muted=!sound.muted}
                                        }
                                        Slider{
                                            id:volumeSlider;objectName:"volumeSlider";Layout.fillWidth:true
                                            from:0;to:1;stepSize:.05;value:sound.volume
                                            Accessible.name:"Уровень громкости"
                                            onMoved:{sound.setVolume(value);sound.setMuted(false)}
                                            background:Rectangle{x:volumeSlider.leftPadding;y:volumeSlider.topPadding+volumeSlider.availableHeight/2-2;width:volumeSlider.availableWidth;height:4;radius:2;color:"#3b3b40";Rectangle{width:volumeSlider.visualPosition*parent.width;height:4;radius:2;color:"#b9b1f0"}}
                                            handle:Rectangle{x:volumeSlider.leftPadding+volumeSlider.visualPosition*(volumeSlider.availableWidth-width);y:volumeSlider.topPadding+volumeSlider.availableHeight/2-5;width:10;height:10;radius:5;color:"#eeeef0"}
                                        }
                                    }
                                }
                            }
                            PButton { anchors.verticalCenter:parent.verticalCenter;text:player.playbackRate+"×";iconName:"chevron-down";iconTrailing:true;iconSize:12;hint:"Скорость воспроизведения";onClicked:speedMenu.open()
                                Menu {
                                    id:speedMenu
                                    Repeater {
                                        model:[.5,.75,1,1.25,1.5,1.75,2]
                                        MenuItem {required property real modelData;text:modelData+"×";checkable:true;checked:player.playbackRate===modelData;onTriggered:player.playbackRate=modelData}
                                    }
                                }
                            }
                            PButton { anchors.verticalCenter:parent.verticalCenter;iconName:root.videoOnly?"minimize":"maximize";width:mediaPane.width<650?32:36;quiet:true;hint:"Полноэкранный режим";enabled:s.hasMedia;onClicked:root.toggleFullScreen() }
                        }
                    }
                    ColumnLayout {
                        visible:s.hasMedia && !root.videoOnly
                        Layout.fillWidth:true;spacing:12
                        RowLayout{
                            Layout.fillWidth:true;spacing:8
                            PButton{objectName:"trimToggle";text:"Обрезка";iconName:"scissors";quiet:true;hint:root.trimOpen?"Свернуть обрезку":"Выделить фрагмент для обрезки";onClicked:root.trimOpen?root.closeTrim():root.openTrim()}
                            Item{Layout.fillWidth:true}
                            PButton{visible:trimOpen;iconName:"circle-minus";quiet:true;hint:"Отдалить дорожку";onClicked:root.zoomFactor=Math.min(50,root.zoomFactor*1.5)}
                            PButton{visible:trimOpen;iconName:"circle-plus";quiet:true;hint:"Приблизить дорожку";onClicked:root.zoomFactor=Math.max(1.15,root.zoomFactor/1.5)}
                            PButton{visible:trimOpen;iconName:"x";quiet:true;hint:"Закрыть обрезку";onClicked:root.closeTrim()}
                        }
                        Waveform{
                            visible:trimOpen;Layout.fillWidth:true;implicitHeight:96
                            peaks:bridge.waveform;duration:root.total;position:player.position/1000
                            viewStart:root.viewStart;viewEnd:root.viewStart+root.viewSpan
                            selectionStart:root.clipStart;selectionEnd:root.clipEnd;editable:true
                            onSeek:seconds=>player.setPosition(seconds*1000)
                            onSelectionEdited:(start,end)=>root.setClip(start,end)
                        }
                        RowLayout{
                            visible:trimOpen;Layout.fillWidth:true;spacing:10
                            TimeField{id:trimStart;objectName:"trimStart";label:"Начало";seconds:root.clipStart;onEdited:value=>root.setClip(value,root.clipEnd)}
                            TimeField{id:trimEnd;objectName:"trimEnd";label:"Конец";seconds:root.clipEnd;onEdited:value=>root.setClip(root.clipStart,value)}
                            ColumnLayout{spacing:6;Layout.leftMargin:3
                                Text{ textFormat: Text.PlainText;text:"Длительность";color:"#a1a1aa";font.family:"Onest";font.pixelSize:11}
                                Text{ textFormat: Text.PlainText;text:trimStart.displayTime(root.clipLength);color:"#b6b6bd";font.family:"Onest";font.pixelSize:12;Layout.bottomMargin:8}
                            }
                            Item{Layout.fillWidth:true}
                            PButton{objectName:"clipPreview";text:mediaPane.width>=750?"Предпросмотр":"";iconName:root.previewing?"pause":"play";hint:root.previewing?"Остановить предпросмотр":"Предпросмотр фрагмента";enabled:root.clipLength>0;onClicked:{if(root.previewing){player.pause();root.previewing=false}else{player.setPosition(root.clipStart*1000);player.play();root.previewing=true}}}
                            PButton{objectName:"saveClip";text:mediaPane.width>=750?"Сохранить фрагмент":"Сохранить";iconName:"arrow-right";primary:true;enabled:!s.busy && root.clipLength>0;hint:"Сохранить выделенный фрагмент";onClicked:bridge.exportClip(root.clipStart,root.clipEnd,player.hasVideo)}
                        }
                    }
                }
            }
            Rectangle {
                color:"#121214"
                visible:!root.videoOnly
                SplitView.preferredWidth:450
                SplitView.minimumWidth:380
                ColumnLayout {
                    anchors.fill:parent;anchors.margins:24;spacing:12
                    RowLayout{
                        Layout.fillWidth:true
                        TabBar {
                            id: sectionTabs
                            implicitWidth: 300
                            implicitHeight: 36
                            Layout.fillWidth: true
                            currentIndex: root.semantic ? 1 : 0
                            onCurrentIndexChanged: root.selectSection(currentIndex===1)
                            spacing: 2
                            background: Rectangle { color: "#080808"; radius: 9 }
                            Repeater {
                                model: ["Расшифровка", "Поиск по смыслу"]
                                TabButton {
                                    required property int index
                                    required property string modelData
                                    objectName: index===0 ? "transcriptTab" : "meaningTab"
                                    width: (sectionTabs.width-2)/2
                                    implicitHeight: 36
                                    hoverEnabled: true
                                    Accessible.name: modelData + (index===1 && s.operation==="semantic" ? ", поиск выполняется" : "")
                                    background: Rectangle {
                                        radius: 8; color: parent.checked ? "#272729" : parent.hovered ? "#1d1d1f" : "transparent"
                                        border.width: parent.visualFocus ? 1 : 0; border.color: "#b9b1f0"
                                    }
                                    contentItem: RowLayout {
                                        spacing: 4
                                        Text { textFormat: Text.PlainText; text: modelData; color: sectionTabs.currentIndex===index ? "#eeeef0" : "#a1a1aa"; font.family: "Onest"; font.pixelSize: 12; font.weight: sectionTabs.currentIndex===index ? Font.Medium : Font.Normal; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter; Layout.fillWidth: true }
                                        BusyIndicator { visible: index===1 && s.operation==="semantic"; running: visible; Layout.preferredWidth: 12; Layout.preferredHeight: 12; palette.dark: "#c8bfef" }
                                    }
                                }
                            }
                        }
                        PButton{iconName:"ellipsis";quiet:true;hint:"Действия с расшифровкой";onClicked:transcriptMenu.open()
                            Menu{id:transcriptMenu
                                MenuItem{text:"Сохранить расшифровку…";enabled:bridge.rows.length>0;onTriggered:bridge.exportTranscript()}
                                MenuItem{text:"Копировать текст";enabled:bridge.rows.length>0;onTriggered:bridge.copyTranscript()}
                                MenuItem{text:"Распознать заново";enabled:s.hasMedia && !s.busy;onTriggered:bridge.transcribe()}
                                MenuItem{text:"Выделить фразу для обрезки";enabled:s.selectedStart>=0;onTriggered:bridge.trimSelection()}
                                MenuSeparator{}
                                MenuItem{text:"Модели и подключение…";onTriggered:bridge.settings()}
                            }
                        }
                    }
                    Text { textFormat: Text.PlainText; visible: !root.semantic; text:s.transcriptReady?"Русский · Готово":s.transcriptPartial?"Русский · Распознаём…":s.operation==="transcribe"?"Русский · Подготовка…":"Появится после распознавания";color:"#a1a1aa";font.family:"Onest";font.pixelSize:12;Layout.fillWidth:true }
                    PField{
                        id:search;objectName:"searchField";Layout.fillWidth:true
                        visible: !root.semantic
                        leftPadding:40;rightPadding:text.length>0?40:58
                        placeholderText:"Найти в тексте"
                        Accessible.name:placeholderText
                        onTextChanged:bridge.findText(text)
                        onAccepted:root.acceptSearch(false)
                        Keys.onPressed:event=>{if((event.key===Qt.Key_Return||event.key===Qt.Key_Enter)&&(event.modifiers&Qt.ShiftModifier)){root.acceptSearch(true);event.accepted=true}}
                        Image{anchors.left:parent.left;anchors.leftMargin:15;anchors.verticalCenter:parent.verticalCenter;width:16;height:16;source:assetRoot+"icons/search.svg";sourceSize:Qt.size(32,32);opacity:.7}
                        PButton{objectName:"clearSearch";visible:search.text.length>0;anchors.right:parent.right;anchors.verticalCenter:parent.verticalCenter;implicitWidth:34;implicitHeight:34;iconName:"x";iconSize:13;quiet:true;hint:"Очистить поиск";onClicked:{search.clear();search.forceActiveFocus()}}
                        Rectangle{visible:search.text.length===0;anchors.right:parent.right;anchors.rightMargin:10;anchors.verticalCenter:parent.verticalCenter;width:31;height:22;radius:5;color:"#272729";Text{ textFormat: Text.PlainText;anchors.centerIn:parent;text:Qt.platform.os==="osx"?"⌘F":"Ctrl F";color:"#b6b6bd";font.family:"Onest";font.pixelSize:10}}
                    }
                    MeaningPanel {
                        id: meaning
                        visible: root.semantic
                        Layout.fillWidth: true; Layout.fillHeight: true
                        config: root.s
                        onShowTranscript: index => { root.selectSection(false); bridge.selectMeaningResult(index) }
                    }
                    Text{ textFormat: Text.PlainText;
                        objectName:"searchFeedback"
                        visible:root.hasQuery
                        text:s.searchCount===0?((s.transcriptPartial||s.operation==="transcribe")?"В готовом тексте совпадений нет. Распознавание продолжается.":"Ничего не найдено. Попробуйте другой запрос."):(s.searchIndex+1)+" из "+s.searchCount
                        color:"#a1a1aa";font.family:"Onest";font.pixelSize:12;Layout.fillWidth:true;wrapMode:Text.WordWrap
                    }
                    ListView{
                        id:transcript
                        objectName:"transcriptView"
                        visible: !root.semantic
                        Layout.fillWidth:true;Layout.fillHeight:true
                        clip:true;spacing:6
                        model:bridge.transcriptModel
                        ScrollBar.vertical:ScrollBar{policy:ScrollBar.AsNeeded}
                        delegate:ItemDelegate{
                            id:row
                            required property var record
                            required property int index
                            property bool current:s.activeRow===index
                            property bool selected:index>=s.selectedStart && index<=s.selectedEnd && s.selectedStart>=0
                            width:ListView.view.width
                            height:rowContent.implicitHeight+20
                            hoverEnabled:true
                            padding:10
                            Accessible.name:record.time+". "+record.text
                            background:Rectangle{radius:9;color:row.selected?"#25232b":row.current?"#202022":row.hovered?"#131315":"transparent"}
                            contentItem:RowLayout{
                                id:rowContent;spacing:12
                                Text{ textFormat: Text.PlainText;text:row.record.time;color:row.current||row.record.match?"#c8bfef":"#a1a1aa";font.family:"Onest";font.pixelSize:12;Layout.alignment:Qt.AlignTop;Layout.preferredWidth:42;Layout.topMargin:2}
                                Text{text:row.record.richText;textFormat:Text.RichText;color:"#eeeef0";font.family:"Onest";font.pixelSize:14;lineHeight:1.38;wrapMode:Text.WordWrap;Layout.fillWidth:true}
                            }
                            onClicked:bridge.selectRowFromPointer(index)
                        }
                        ColumnLayout{
                            visible:bridge.rows.length===0
                            anchors.centerIn:parent;width:parent.width-30;spacing:14
                            Image{source:assetRoot+"icons/file-text.svg";sourceSize:Qt.size(27,27);Layout.preferredWidth:27;Layout.preferredHeight:27;opacity:.55;Layout.alignment:Qt.AlignHCenter}
                            Text{ textFormat: Text.PlainText;text:s.operation==="transcribe"?"Распознаём первые фразы…":s.hasMedia?"Здесь будет текст записи":"Текст рядом с записью";color:"#b6b6bd";font.family:"Onest";font.pixelSize:14;wrapMode:Text.WordWrap;Layout.fillWidth:true;horizontalAlignment:Text.AlignHCenter}
                            Text{ textFormat: Text.PlainText;text:"Нажмите на фразу — плеер перейдёт\nк соответствующему моменту.";color:"#a1a1aa";font.family:"Onest";font.pixelSize:12;lineHeight:1.5;horizontalAlignment:Text.AlignHCenter;Layout.alignment:Qt.AlignHCenter}
                            PButton{visible:s.hasMedia&&!s.busy;text:s.asrReady?"Распознать речь":"Настроить распознавание";onClicked:s.asrReady?bridge.transcribe():bridge.settings();Layout.alignment:Qt.AlignHCenter}
                        }
                    }
                    RowLayout{
                        visible: !root.semantic
                        Layout.fillWidth:true;spacing:9
                        Switch{
                            id:follow;checked:true;onToggled:root.followText=checked
                            Accessible.name:"Следовать за воспроизведением"
                            implicitWidth:36;implicitHeight:24
                            indicator:Rectangle{
                                width:34;height:20;radius:10;y:2;color:follow.checked?"#8c75bb":"#343437"
                                Rectangle{x:follow.checked?16:3;y:3;width:14;height:14;radius:7;color:"#f2eff9";Behavior on x{NumberAnimation{duration:240;easing.type:Easing.OutCubic}}}
                            }
                        }
                        Text{ textFormat: Text.PlainText;text:"Следовать за записью";color:"#b6b6bd";font.family:"Onest";font.pixelSize:12;Layout.fillWidth:true}
                        PButton{objectName:"previousResult";iconName:"chevron-left";implicitWidth:36;hint:root.hasQuery?"Предыдущий результат · Shift+Enter":"Предыдущая фраза";enabled:root.hasQuery?root.resultsCurrent&&s.searchCount>0:bridge.rows.length>0;onClicked:bridge.navigateTranscript(-1)}
                        PButton{objectName:"nextResult";iconName:"chevron-right";implicitWidth:36;hint:root.hasQuery?"Следующий результат · Enter":"Следующая фраза";enabled:root.hasQuery?root.resultsCurrent&&s.searchCount>0:bridge.rows.length>0;onClicked:bridge.navigateTranscript(1)}
                    }
                }
            }
        }
        RowLayout{
            Layout.fillWidth:true;Layout.leftMargin:24;Layout.rightMargin:20;Layout.topMargin:6;Layout.bottomMargin:6;spacing:12
            Text{ textFormat: Text.PlainText;text:root.semantic&&s.operation==="semantic"?"Можно вернуться к расшифровке — поиск продолжится в фоне":s.status;color:"#a1a1aa";font.family:"Onest";font.pixelSize:11;elide:Text.ElideRight;Layout.fillWidth:true}
            Text{ textFormat: Text.PlainText;visible:s.busy&&s.fraction>=0&&!(root.semantic&&s.operation==="semantic");text:Math.round(s.fraction*100)+"%";color:"#c8bfef";font.family:"Onest";font.pixelSize:11}
            PButton{visible:s.busy&&!(root.semantic&&s.operation==="semantic");iconName:"x";quiet:true;implicitHeight:24;implicitWidth:24;iconSize:13;hint:"Отменить обработку";onClicked:bridge.cancelOperation()}
            PButton{visible:!s.busy&&s.lastExport.length>0;text:"Показать файл";quiet:true;implicitHeight:24;onClicked:bridge.revealExport()}
            Image{source:assetRoot+"icons/monitor.svg";sourceSize:Qt.size(13,13);Layout.preferredWidth:13;Layout.preferredHeight:13;opacity:.65}
            Text{ textFormat: Text.PlainText;text:"Локально";color:"#a1a1aa";font.family:"Onest";font.pixelSize:11}
        }
    }
    Setup{anchors.fill:parent;config:root.s;visible:s.settingsOpen&&!s.onboarding}
    Onboarding{anchors.fill:parent;config:root.s;visible:s.onboarding}
}

