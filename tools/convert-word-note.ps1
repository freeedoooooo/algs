param(
    [Parameter(Mandatory = $true)]
    [string]$SourceDocx,

    [Parameter(Mandatory = $true)]
    [string]$OutputRoot
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function New-List {
    return ,([System.Collections.ArrayList]::new())
}

function Add-Block {
    param(
        $Blocks,
        [string]$Kind,
        [string]$Text,
        [string]$AssetPath
    )

    if ($Kind -eq 'text' -and [string]::IsNullOrWhiteSpace($Text)) {
        return
    }

    [void]$Blocks.Add([pscustomobject]@{
            Kind      = $Kind
            Text      = $Text
            AssetPath = $AssetPath
        })
}

function Get-SafeName {
    param(
        [string]$Text,
        [int]$MaxLength = 60
    )

    $safe = if ($null -eq $Text) { '' } else { $Text.Trim() }
    if ([string]::IsNullOrWhiteSpace($safe)) {
        return 'untitled'
    }

    $safe = $safe -replace '^[☒☐]\s*', ''
    $safe = $safe -replace '[<>:"/\\|?*]', ' '
    $safe = $safe -replace '[`'']', ''
    $safe = $safe -replace '[\[\]\(\)（）【】{}《》<>]', ' '
    $safe = $safe -replace '[,，、；;：:！？!?.。]+', '-'
    $safe = $safe -replace '\s+', '-'
    $safe = $safe.Trim(' ', '-', '.')

    if ($safe.Length -gt $MaxLength) {
        $safe = $safe.Substring(0, $MaxLength).Trim(' ', '-', '.')
    }

    if ([string]::IsNullOrWhiteSpace($safe)) {
        return 'untitled'
    }

    return $safe
}

function Get-RelativeMarkdownPath {
    param(
        [string]$FromDirectory,
        [string]$ToPath
    )

    $fromFull = [System.IO.Path]::GetFullPath($FromDirectory)
    if (-not $fromFull.EndsWith([System.IO.Path]::DirectorySeparatorChar)) {
        $fromFull += [System.IO.Path]::DirectorySeparatorChar
    }

    $toFull = [System.IO.Path]::GetFullPath($ToPath)
    $fromUri = [System.Uri]::new($fromFull)
    $toUri = [System.Uri]::new($toFull)
    return [System.Uri]::UnescapeDataString($fromUri.MakeRelativeUri($toUri).ToString())
}

function Write-Utf8File {
    param(
        [string]$Path,
        [string[]]$Lines
    )

    $directory = Split-Path -Parent $Path
    if (-not [string]::IsNullOrWhiteSpace($directory)) {
        New-Item -ItemType Directory -Force -Path $directory | Out-Null
    }

    $content = ($Lines -join "`r`n").TrimEnd()
    [System.IO.File]::WriteAllText($Path, $content + "`r`n", [System.Text.UTF8Encoding]::new($false))
}

function Add-Line {
    param(
        $Lines,
        [string]$Text
    )

    [void]$Lines.Add($Text)
}

function Add-BlankLine {
    param($Lines)

    if ($Lines.Count -eq 0) {
        return
    }

    if ($Lines[$Lines.Count - 1] -ne '') {
        [void]$Lines.Add('')
    }
}

function Convert-BlocksToLines {
    param(
        $Blocks,
        [string]$CurrentDirectory
    )

    $lines = New-List
    foreach ($block in $Blocks) {
        switch ($block.Kind) {
            'text' {
                Add-BlankLine $lines
                Add-Line $lines $block.Text
            }
            'image' {
                Add-BlankLine $lines
                $relativePath = Get-RelativeMarkdownPath -FromDirectory $CurrentDirectory -ToPath $block.AssetPath
                Add-Line $lines "![配图]($relativePath)"
            }
            'subheading' {
                Add-BlankLine $lines
                Add-Line $lines "### $($block.Text)"
            }
        }
    }

    while ($lines.Count -gt 0 -and $lines[$lines.Count - 1] -eq '') {
        $lines.RemoveAt($lines.Count - 1)
    }

    return ,$lines
}

function Get-TargetBlocks {
    param(
        $DocumentModel,
        $CurrentSection,
        $CurrentChapter,
        $CurrentTopic
    )

    if ($null -ne $CurrentTopic) {
        return ,$CurrentTopic.Blocks
    }

    if ($null -ne $CurrentChapter) {
        return ,$CurrentChapter.Blocks
    }

    if ($null -ne $CurrentSection) {
        return ,$CurrentSection.IntroBlocks
    }

    return ,$DocumentModel.IntroBlocks
}

function Resolve-WordTargetKey {
    param([string]$Target)

    $normalized = $Target.Replace('\', '/')
    if ($normalized.StartsWith('/')) {
        return $normalized.TrimStart('/')
    }

    while ($normalized.StartsWith('../')) {
        $normalized = $normalized.Substring(3)
    }

    if ($normalized.StartsWith('word/')) {
        return $normalized
    }

    return "word/$normalized"
}

function Get-MainCategoryName {
    param([string]$SectionTitle)

    switch ($SectionTitle) {
        '基础巩固' { return '基础巩固' }
        '算法大厂面试真题' { return '大厂真题' }
        '基础提升' { return '基础提升' }
        '中级提升' { return '中级提升' }
        default { return $null }
    }
}

if (-not (Test-Path -LiteralPath $SourceDocx)) {
    throw "Source docx not found: $SourceDocx"
}

Add-Type -AssemblyName System.IO.Compression.FileSystem

New-Item -ItemType Directory -Force -Path $OutputRoot | Out-Null
$assetsDirectory = Join-Path $OutputRoot 'assets'
New-Item -ItemType Directory -Force -Path $assetsDirectory | Out-Null

$zip = [System.IO.Compression.ZipFile]::OpenRead((Resolve-Path -LiteralPath $SourceDocx).Path)
try {
    $documentEntry = $zip.GetEntry('word/document.xml')
    $relsEntry = $zip.GetEntry('word/_rels/document.xml.rels')

    if ($null -eq $documentEntry -or $null -eq $relsEntry) {
        throw 'The docx file is missing required Word XML entries.'
    }

    $documentReader = [System.IO.StreamReader]::new($documentEntry.Open())
    $relsReader = [System.IO.StreamReader]::new($relsEntry.Open())
    try {
        [xml]$documentXml = $documentReader.ReadToEnd()
        [xml]$relsXml = $relsReader.ReadToEnd()
    }
    finally {
        $documentReader.Close()
        $relsReader.Close()
    }

    $relationshipMap = @{}
    foreach ($relationship in $relsXml.Relationships.Relationship) {
        $relationshipMap[[string]$relationship.Id] = [string]$relationship.Target
    }

    $assetMap = @{}
    foreach ($entry in $zip.Entries) {
        if ($entry.FullName -like 'word/media/*' -and -not $entry.FullName.EndsWith('/')) {
            $fileName = Split-Path -Leaf $entry.FullName
            $destination = Join-Path $assetsDirectory $fileName
            $inputStream = $entry.Open()
            $outputStream = [System.IO.File]::Create($destination)
            try {
                $inputStream.CopyTo($outputStream)
            }
            finally {
                $outputStream.Dispose()
                $inputStream.Dispose()
            }

            $assetMap[$entry.FullName.Replace('\', '/')] = $destination
        }
    }

    $ns = [System.Xml.XmlNamespaceManager]::new($documentXml.NameTable)
    $ns.AddNamespace('w', 'http://schemas.openxmlformats.org/wordprocessingml/2006/main')
    $ns.AddNamespace('a', 'http://schemas.openxmlformats.org/drawingml/2006/main')
    $ns.AddNamespace('r', 'http://schemas.openxmlformats.org/officeDocument/2006/relationships')

    $paragraphNodes = $documentXml.SelectNodes('//w:body/w:p', $ns)

    $documentModel = [pscustomobject]@{
        Title       = '04 算法'
        IntroBlocks = $null
        Sections    = $null
    }
    $documentModel.IntroBlocks = New-List
    $documentModel.Sections = New-List

    $currentSection = $null
    $currentChapter = $null
    $currentTopic = $null
    $currentSubsection = $null
    $chapterCounter = 0

    foreach ($paragraphNode in $paragraphNodes) {
        $styleNode = $paragraphNode.SelectSingleNode('./w:pPr/w:pStyle', $ns)
        $style = if ($null -ne $styleNode) { [string]$styleNode.val } else { '' }

        $textParts = @($paragraphNode.SelectNodes('.//w:t', $ns) | ForEach-Object { $_.InnerText })
        $paragraphText = (($textParts -join '') -replace '\s+', ' ').Trim()

        $imageRids = @($paragraphNode.SelectNodes('.//a:blip', $ns) | ForEach-Object { [string]$_.embed } | Where-Object { $_ })

        if ($style -in @('1', 'Heading1')) {
            if ([string]::IsNullOrWhiteSpace($paragraphText)) {
                continue
            }

            $currentSection = [pscustomobject]@{
                Title       = $paragraphText
                IntroBlocks = $null
                Chapters    = $null
            }
            $currentSection.IntroBlocks = New-List
            $currentSection.Chapters = New-List

            [void]$documentModel.Sections.Add($currentSection)
            $currentChapter = $null
            $currentTopic = $null
            $currentSubsection = $null
            continue
        }

        if ($style -in @('2', 'Heading2')) {
            if ([string]::IsNullOrWhiteSpace($paragraphText)) {
                continue
            }

            if ($null -eq $currentSection) {
                $currentSection = [pscustomobject]@{
                    Title       = '未分类'
                    IntroBlocks = $null
                    Chapters    = $null
                }
                $currentSection.IntroBlocks = New-List
                $currentSection.Chapters = New-List
                [void]$documentModel.Sections.Add($currentSection)
            }

            $chapterCounter++
            $currentChapter = [pscustomobject]@{
                Index           = $chapterCounter
                Title           = $paragraphText
                SectionTitle    = $currentSection.Title
                Blocks          = $null
                Topics          = $null
                CurrentSubTitle = ''
                DirectoryName   = ''
                DirectoryPath   = ''
                ReadmePath      = ''
            }
            $currentChapter.Blocks = New-List
            $currentChapter.Topics = New-List

            [void]$currentSection.Chapters.Add($currentChapter)
            $currentTopic = $null
            $currentSubsection = $null
            continue
        }

        if ($style -in @('3', 'Heading3')) {
            if ($null -ne $currentChapter -and -not [string]::IsNullOrWhiteSpace($paragraphText)) {
                $currentSubsection = $paragraphText
                Add-Block -Blocks $currentChapter.Blocks -Kind 'subheading' -Text $paragraphText
                $currentTopic = $null
            }
            continue
        }

        $topicMatch = [regex]::Match($paragraphText, '^(?<mark>[☒☐])\s*(?<title>.+)$')
        if ($topicMatch.Success) {
            if ($null -eq $currentChapter -and $null -ne $currentSection) {
                $chapterCounter++
                $currentChapter = [pscustomobject]@{
                    Index           = $chapterCounter
                    Title           = $currentSection.Title
                    SectionTitle    = $currentSection.Title
                    Blocks          = $null
                    Topics          = $null
                    CurrentSubTitle = ''
                    DirectoryName   = ''
                    DirectoryPath   = ''
                    ReadmePath      = ''
                }
                $currentChapter.Blocks = New-List
                $currentChapter.Topics = New-List
                [void]$currentSection.Chapters.Add($currentChapter)
            }

            if ($null -eq $currentChapter) {
                continue
            }

            $statusMark = $topicMatch.Groups['mark'].Value
            $topicTitle = $topicMatch.Groups['title'].Value.Trim()

            $currentTopic = [pscustomobject]@{
                Index           = $($currentChapter.Topics.Count + 1)
                Title           = $topicTitle
                RawMarker       = $statusMark
                StatusText      = $(if ($statusMark -eq '☒') { '已标记完成' } else { '待补充' })
                SectionTitle    = $currentChapter.SectionTitle
                ChapterTitle    = $currentChapter.Title
                SubsectionTitle = $currentSubsection
                Blocks          = $null
                FileName        = ''
                FilePath        = ''
            }
            $currentTopic.Blocks = New-List

            [void]$currentChapter.Topics.Add($currentTopic)
            continue
        }

        $targetBlocks = Get-TargetBlocks -DocumentModel $documentModel -CurrentSection $currentSection -CurrentChapter $currentChapter -CurrentTopic $currentTopic

        if (-not [string]::IsNullOrWhiteSpace($paragraphText)) {
            Add-Block -Blocks $targetBlocks -Kind 'text' -Text $paragraphText
        }

        foreach ($imageRid in $imageRids) {
            if (-not $relationshipMap.ContainsKey($imageRid)) {
                continue
            }

            $targetKey = Resolve-WordTargetKey -Target $relationshipMap[$imageRid]
            if ($assetMap.ContainsKey($targetKey)) {
                Add-Block -Blocks $targetBlocks -Kind 'image' -AssetPath $assetMap[$targetKey]
            }
        }
    }
}
finally {
    $zip.Dispose()
}

foreach ($section in $documentModel.Sections) {
    $section | Add-Member -NotePropertyName CategoryName -NotePropertyValue (Get-MainCategoryName -SectionTitle $section.Title) -Force
    $section | Add-Member -NotePropertyName SectionDirectoryPath -NotePropertyValue $null -Force
    $section | Add-Member -NotePropertyName SectionReadmePath -NotePropertyValue $null -Force
}

$mainSectionOrder = @('基础巩固', '大厂真题', '基础提升', '中级提升')
$mainSections = New-List
foreach ($categoryName in $mainSectionOrder) {
    $matchingSection = $documentModel.Sections | Where-Object { $_.CategoryName -eq $categoryName } | Select-Object -First 1
    if ($null -ne $matchingSection) {
        [void]$mainSections.Add($matchingSection)
    }
}

foreach ($section in $mainSections) {
    $section.SectionDirectoryPath = Join-Path $OutputRoot $section.CategoryName
    $section.SectionReadmePath = Join-Path $section.SectionDirectoryPath 'README.md'
    New-Item -ItemType Directory -Force -Path $section.SectionDirectoryPath | Out-Null

    foreach ($chapter in $section.Chapters) {
        $chapterNumberMatch = [regex]::Match($chapter.Title, '^\s*(\d+)\s+(.+)$')
        if ($chapterNumberMatch.Success) {
            $chapterFolderName = '{0:D2}-{1}' -f [int]$chapterNumberMatch.Groups[1].Value, (Get-SafeName -Text $chapterNumberMatch.Groups[2].Value -MaxLength 48)
        }
        else {
            $chapterFolderName = '{0:D2}-{1}' -f [int]$chapter.Index, (Get-SafeName -Text $chapter.Title -MaxLength 48)
        }

        $chapter.DirectoryName = $chapterFolderName
        $chapter.DirectoryPath = Join-Path $section.SectionDirectoryPath $chapterFolderName
        $chapter.ReadmePath = Join-Path $chapter.DirectoryPath 'README.md'
        New-Item -ItemType Directory -Force -Path $chapter.DirectoryPath | Out-Null

        $usedFileNames = @{}
        foreach ($topic in $chapter.Topics) {
            $baseName = '{0:D2}-{1}.md' -f [int]$topic.Index, (Get-SafeName -Text $topic.Title -MaxLength 52)
            $candidate = $baseName
            $suffix = 2
            while ($usedFileNames.ContainsKey($candidate)) {
                $stem = [System.IO.Path]::GetFileNameWithoutExtension($baseName)
                $candidate = '{0}-{1}.md' -f $stem, $suffix
                $suffix++
            }

            $usedFileNames[$candidate] = $true
            $topic.FileName = $candidate
            $topic.FilePath = Join-Path $chapter.DirectoryPath $candidate
        }
    }
}

$mainReadmeLines = New-List
Add-Line $mainReadmeLines '# 04 算法'
Add-BlankLine $mainReadmeLines
Add-Line $mainReadmeLines '由原始 Word 笔记拆分整理为 Markdown 目录、章节页与题目页。'
Add-Line $mainReadmeLines '当前按四个主目录组织：基础巩固、大厂真题、基础提升、中级提升。'
Add-Line $mainReadmeLines '所有链接均使用相对路径，生成内容均保留在 `my-notes` 目录下。'

$introLines = Convert-BlocksToLines -Blocks $documentModel.IntroBlocks -CurrentDirectory $OutputRoot
if ($introLines.Count -gt 0) {
    Add-BlankLine $mainReadmeLines
    Add-Line $mainReadmeLines '## 说明'
    foreach ($line in $introLines) {
        Add-Line $mainReadmeLines $line
    }
}

foreach ($section in $documentModel.Sections | Where-Object { -not $_.CategoryName }) {
    Add-BlankLine $mainReadmeLines
    Add-Line $mainReadmeLines "## $($section.Title)"
    $sectionIntroLines = Convert-BlocksToLines -Blocks $section.IntroBlocks -CurrentDirectory $OutputRoot
    foreach ($line in $sectionIntroLines) {
        Add-Line $mainReadmeLines $line
    }
}

Add-BlankLine $mainReadmeLines
Add-Line $mainReadmeLines '## 四大目录'
foreach ($section in $mainSections) {
    $relativeSectionReadme = Get-RelativeMarkdownPath -FromDirectory $OutputRoot -ToPath $section.SectionReadmePath
    $chapterCount = $section.Chapters.Count
    $topicCount = @($section.Chapters | ForEach-Object { $_.Topics.Count } | Measure-Object -Sum).Sum
    Add-Line $mainReadmeLines "- [$($section.CategoryName)]($relativeSectionReadme)（章节：$chapterCount，条目：$topicCount）"
}

Write-Utf8File -Path (Join-Path $OutputRoot 'README.md') -Lines $mainReadmeLines

foreach ($section in $mainSections) {
    $sectionReadmeLines = New-List
    Add-Line $sectionReadmeLines "# $($section.CategoryName)"
    Add-BlankLine $sectionReadmeLines
    Add-Line $sectionReadmeLines '[返回总目录](../README.md)'
    Add-BlankLine $sectionReadmeLines
    Add-Line $sectionReadmeLines "- 章节数量：$($section.Chapters.Count)"
    Add-Line $sectionReadmeLines "- 条目数量：$((@($section.Chapters | ForEach-Object { $_.Topics.Count } | Measure-Object -Sum).Sum))"

    $sectionIntroLines = Convert-BlocksToLines -Blocks $section.IntroBlocks -CurrentDirectory $section.SectionDirectoryPath
    if ($sectionIntroLines.Count -gt 0) {
        Add-BlankLine $sectionReadmeLines
        Add-Line $sectionReadmeLines '## 分类说明'
        foreach ($line in $sectionIntroLines) {
            Add-Line $sectionReadmeLines $line
        }
    }

    Add-BlankLine $sectionReadmeLines
    Add-Line $sectionReadmeLines '## 章节目录'
    foreach ($chapter in $section.Chapters) {
        $relativeChapterReadme = Get-RelativeMarkdownPath -FromDirectory $section.SectionDirectoryPath -ToPath $chapter.ReadmePath
        Add-Line $sectionReadmeLines "- [$($chapter.Title)]($relativeChapterReadme)"
    }

    Write-Utf8File -Path $section.SectionReadmePath -Lines $sectionReadmeLines

    foreach ($chapter in $section.Chapters) {
        $chapterLines = New-List
        Add-Line $chapterLines "# $($chapter.Title)"
        Add-BlankLine $chapterLines
        Add-Line $chapterLines '[返回分类](../README.md) | [返回总目录](../../README.md)'
        Add-BlankLine $chapterLines
        Add-Line $chapterLines "- 所属分类：$($section.CategoryName)"
        Add-Line $chapterLines "- 条目数量：$($chapter.Topics.Count)"

        Add-BlankLine $chapterLines
        Add-Line $chapterLines '## 条目目录'
        foreach ($topic in $chapter.Topics) {
            $relativeTopicPath = Get-RelativeMarkdownPath -FromDirectory $chapter.DirectoryPath -ToPath $topic.FilePath
            Add-Line $chapterLines "- [$($topic.Title)]($relativeTopicPath)"
        }

        $chapterBlockLines = Convert-BlocksToLines -Blocks $chapter.Blocks -CurrentDirectory $chapter.DirectoryPath
        if ($chapterBlockLines.Count -gt 0) {
            Add-BlankLine $chapterLines
            Add-Line $chapterLines '## 章节笔记'
            foreach ($line in $chapterBlockLines) {
                Add-Line $chapterLines $line
            }
        }

        Write-Utf8File -Path $chapter.ReadmePath -Lines $chapterLines

        foreach ($topic in $chapter.Topics) {
            $topicLines = New-List
            Add-Line $topicLines "# $($topic.Title)"
            Add-BlankLine $topicLines
            Add-Line $topicLines '[返回章节](./README.md) | [返回分类](../README.md) | [返回总目录](../../README.md)'
            Add-BlankLine $topicLines
            Add-Line $topicLines "- 状态：$($topic.StatusText)"
            Add-Line $topicLines "- 所属分类：$($section.CategoryName)"
            Add-Line $topicLines "- 所属章节：$($topic.ChapterTitle)"
            if (-not [string]::IsNullOrWhiteSpace($topic.SubsectionTitle)) {
                Add-Line $topicLines "- 所属小节：$($topic.SubsectionTitle)"
            }
            Add-Line $topicLines "- 原始条目：$($topic.RawMarker) $($topic.Title)"

            Add-BlankLine $topicLines
            Add-Line $topicLines '## 笔记'

            $topicBlockLines = Convert-BlocksToLines -Blocks $topic.Blocks -CurrentDirectory $chapter.DirectoryPath
            if ($topicBlockLines.Count -eq 0) {
                Add-Line $topicLines '原始笔记中仅记录了题目名称，暂无额外说明。'
            }
            else {
                foreach ($line in $topicBlockLines) {
                    Add-Line $topicLines $line
                }
            }

            Write-Utf8File -Path $topic.FilePath -Lines $topicLines
        }
    }
}

$summary = [pscustomobject]@{
    OutputRoot    = $OutputRoot
    SectionCount  = $documentModel.Sections.Count
    MainDirCount  = $mainSections.Count
    ChapterCount  = $(@($mainSections | ForEach-Object { $_.Chapters.Count } | Measure-Object -Sum).Sum)
    TopicCount    = $(@($mainSections | ForEach-Object { $_.Chapters } | ForEach-Object { $_.Topics.Count } | Measure-Object -Sum).Sum)
    AssetCount    = $((Get-ChildItem -LiteralPath $assetsDirectory -File | Measure-Object).Count)
    MainReadme    = $(Join-Path $OutputRoot 'README.md')
}

$summary | ConvertTo-Json -Depth 4
