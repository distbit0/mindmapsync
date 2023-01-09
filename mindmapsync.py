import xml.etree.ElementTree as ET
from xml.dom import minidom
import os
import time
import glob
import json
from datetime import datetime
import shutil


def calcIndent(line):
    return line.count("\t")


def getConfig():
    configFileName = "config.json"
    with open(configFileName) as config:
        return json.load(config)


def lastRunTime(action):
    lastRunTimeFile = getConfig()["lastRunTimeFile"]
    if action == "update":
        currentTime = time.time()
        with open(lastRunTimeFile, "w") as lastRunTime:
            lastRunTime.write(str(currentTime))
    if action == "get":
        with open(lastRunTimeFile, "r") as lastRunTime:
            return int(lastRunTime.read().strip().split(".")[0])


def addChildToNode(contents, colour, parentNode, counter):
    nodesList = ET.SubElement(parentNode, "nodes")
    childNode = ET.SubElement(
        nodesList,
        "node",
        id=str(counter),
        posx="0",
        posy="0",
        maxwidth="200",
        width="0",
        height="0",
        side="right",
        fold="false",
        treesize="10000000",
        layout="Horizontal",
        color=str(colour.lower()),
    )
    style = ET.SubElement(
        childNode,
        "style",
        linktype="curved",
        linkwidth="8",
        linkarrow="false",
        linkdash="solid",
        nodeborder="rounded",
        nodewidth="200",
        nodeborderwidth="4",
        nodefill="false",
        nodemargin="20",
        nodepadding="20",
        nodefont="Sans 15",
        nodemarkup="true",
    )
    nodename = ET.SubElement(childNode, "nodename")
    nodenote = ET.SubElement(childNode, "nodenote")
    nodename.text = contents
    nodenote.text = ""
    return childNode


def parseTextFile(text, rootNodeName):
    lines = [("\t" + line) for line in text.split("\n") if line.strip() != ""]
    lines.insert(0, rootNodeName)
    rootElement = ET.Element("a")
    colourChoice = 0
    tree = [rootElement]
    brightColours = getConfig()["brightColours"]
    colour = brightColours[colourChoice]
    for counter, line in enumerate(lines):
        indent = calcIndent(line)
        if indent == 1:
            colourChoice += 1
            colour = brightColours[colourChoice % len(brightColours)]

        lastBranch = tree
        contents = line.strip("\t").strip("-").strip()
        for i in range(indent):
            lastBranch = lastBranch[-1]
        parentNode = lastBranch[0]
        childNode = addChildToNode(contents, colour, parentNode, counter)
        lastBranch.append([childNode])

    return rootElement[0]


def updateGraphFile(inputTextFileName, outputGraphFileName):
    rootNodeName = inputTextFileName.split("/")[-1].split(".")[0]

    inputText = open(inputTextFileName, "r").read()

    xmlTemplate = open("minderxmltemplate.xml").read()
    mainXml = ET.fromstring(xmlTemplate)
    inputTextAsXML = parseTextFile(inputText, rootNodeName)
    mainXml.append(inputTextAsXML)

    xmlstr = minidom.parseString(ET.tostring(mainXml)).toprettyxml(indent="   ")

    with open(outputGraphFileName, "w") as outputFile:
        outputFile.write(xmlstr)


def iterateOverXMLWithDepth(element, tag=None):
    stack = []
    stack.append(iter([element]))
    while stack:
        e = next(stack[-1], None)
        if e == None:
            stack.pop()
        else:
            stack.append(iter(e))
            if tag == None or e.tag == tag:
                yield (e, len(stack) - 1)


def backupFile(outputTextFileName):
    backupFolder = getConfig()["backupsFolder"]
    now = datetime.now()
    dt_string = now.strftime("%d/%m/%Y %H:%M:%S").replace("/", "_")
    fileNamePure = outputTextFileName.split("/")[-1].split(".")[0]
    backupFileName = backupFolder + "/" + fileNamePure + dt_string + ".md"
    shutil.copy(outputTextFileName, backupFileName)


def deleteOldBackups():
    backupFolder = getConfig()["backupsFolder"]
    maxBackupFiles = getConfig()["maxBackupFiles"]
    backupFiles = sorted(
        [os.path.abspath(f) for f in glob.glob(backupFolder + "/*")],
        key=os.path.getctime,
    )
    fileCount = len(backupFiles)
    if fileCount > maxBackupFiles:
        for backupFile in backupFiles[: (fileCount - maxBackupFiles)]:
            os.remove(os.path.abspath(backupFile))


def updateTextFile(inputGraphFileName, outputTextFileName):
    inputGraphFile = open(inputGraphFileName).read()
    mainXml = ET.fromstring(inputGraphFile)

    firstLine = True
    outputTextList = []
    topicText = ""
    for element, depth in iterateOverXMLWithDepth(mainXml, "nodename"):
        realDepth = int(((depth - 4) / 2) - 1)
        if firstLine:
            firstLine = False
            continue
        if realDepth == 0:
            outputTextList.append(topicText)
            topicText = ""

        topicText += "\t" * realDepth + "- " + element.text + "\n"

    outputTextList.append(topicText)
    outputTextList = sorted(outputTextList)
    outputText = "\n\n".join(outputTextList)
    outputText = outputText.strip("\n")

    backupFile(outputTextFileName)

    with open(outputTextFileName, "w") as outputTextFile:
        outputTextFile.write(outputText)


def syncFilePair(textFileName, graphFileName):
    try:
        textFileLastModified = os.path.getmtime(textFileName)
    except OSError:
        textFileLastModified = 0
        with open(textFileName, "w+") as textFile:
            pass  # create the file
    try:
        graphFileLastModified = os.path.getmtime(graphFileName)
    except OSError:
        graphFileLastModified = 0
        with open(graphFileName, "w+") as graphFile:
            pass  # create the file
    lastSyncTime = lastRunTime("get") + 5
    if graphFileLastModified == textFileLastModified == 0:
        # print("both last mod time 0")
        return
    if (lastSyncTime > graphFileLastModified) and (lastSyncTime > textFileLastModified):
        # print("already syned")
        return
    if textFileLastModified > graphFileLastModified:
        # print("graph file updated", "graph:", graphFileName, "text:", textFileName)
        updateGraphFile(textFileName, graphFileName)
    else:
        # print("text file updated", "graph:", graphFileName, "text:", textFileName)
        updateTextFile(graphFileName, textFileName)
    lastRunTime("update")


def syncAllFiles():
    mindmapFolder = getConfig()["mindmapFolder"]
    markdownListFileName = getConfig()["markdownListFile"]
    with open(markdownListFileName) as markdownListFile:
        markdownList = markdownListFile.read().strip().split("\n")
    for markdownFile in markdownList:
        fileName = markdownFile.split("/")[-1].split(".")[0]
        # print("syncing: ", markdownFile, mindmapFolder + "/" + fileName + ".minder")
        syncFilePair(markdownFile, mindmapFolder + "/" + fileName + ".minder")


if __name__ == "__main__":
    syncAllFiles()
    deleteOldBackups()
    time.sleep(30)
    syncAllFiles()
    deleteOldBackups()
