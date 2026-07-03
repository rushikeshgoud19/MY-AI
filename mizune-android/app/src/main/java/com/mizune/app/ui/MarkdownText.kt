package com.mizune.app.ui

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.withStyle
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

@Composable
fun MarkdownText(
    text: String,
    modifier: Modifier = Modifier,
    color: Color = Color.White,
    style: androidx.compose.ui.text.TextStyle = MaterialTheme.typography.bodyMedium
) {
    val parsed = parseMarkdown(text, color, style)

    Column(modifier = modifier) {
        parsed.forEach { block ->
            when (block) {
                is MarkdownBlock.Paragraph -> {
                    Text(
                        text = block.annotatedString,
                        style = style,
                        modifier = Modifier.padding(vertical = 2.dp)
                    )
                }
                is MarkdownBlock.Bullet -> {
                    Text(
                        text = "• ${block.text}",
                        style = style.copy(color = color),
                        modifier = Modifier.padding(start = 8.dp, top = 1.dp, bottom = 1.dp)
                    )
                }
                is MarkdownBlock.CodeBlock -> {
                    Text(
                        text = block.text,
                        style = style.copy(
                            color = Color(0xFF4FC3F7),
                            fontFamily = FontFamily.Monospace,
                            fontSize = style.fontSize * 0.9f
                        ),
                        modifier = Modifier.padding(vertical = 4.dp)
                    )
                }
            }
        }
    }
}

private sealed class MarkdownBlock {
    data class Paragraph(val annotatedString: AnnotatedString) : MarkdownBlock()
    data class Bullet(val text: String) : MarkdownBlock()
    data class CodeBlock(val text: String) : MarkdownBlock()
}

private fun parseMarkdown(
    text: String,
    color: Color,
    style: androidx.compose.ui.text.TextStyle
): List<MarkdownBlock> {
    val blocks = mutableListOf<MarkdownBlock>()
    val lines = text.lines()
    var i = 0

    while (i < lines.size) {
        val line = lines[i]

        // Code block start
        if (line.trimStart().startsWith("```")) {
            val codeLines = mutableListOf<String>()
            i++
            while (i < lines.size && !lines[i].trimStart().startsWith("```")) {
                codeLines.add(lines[i])
                i++
            }
            blocks.add(MarkdownBlock.CodeBlock(codeLines.joinToString("\n")))
            i++
            continue
        }

        // Bullet list
        if (line.trimStart().startsWith("- ") || line.trimStart().startsWith("* ")) {
            blocks.add(MarkdownBlock.Bullet(line.trimStart().removePrefix("- ").removePrefix("* ")))
            i++
            continue
        }

        // Regular paragraph
        val paragraphLines = mutableListOf<String>()
        while (i < lines.size && lines[i].isNotBlank() &&
            !lines[i].trimStart().startsWith("```") &&
            !(lines[i].trimStart().startsWith("- ") || lines[i].trimStart().startsWith("* "))
        ) {
            paragraphLines.add(lines[i])
            i++
        }

        if (paragraphLines.isNotEmpty()) {
            val paragraphText = paragraphLines.joinToString(" ")
            blocks.add(MarkdownBlock.Paragraph(parseInlineMarkdown(paragraphText, color, style)))
        } else {
            i++
        }
    }

    return blocks
}

private fun parseInlineMarkdown(
    text: String,
    color: Color,
    style: androidx.compose.ui.text.TextStyle
): AnnotatedString {
    return buildAnnotatedString {
        val boldRegex = """(\*\*|__)(.+?)\1""".toRegex()
        val italicRegex = """(\*|_)(.+?)\1""".toRegex()
        val codeRegex = """`([^`]+)`""".toRegex()

        var currentIndex = 0
        val tokens = mutableListOf<InlineToken>()

        boldRegex.findAll(text).forEach { tokens.add(InlineToken(it.range.first, it.range.last + 1, TokenType.BOLD, it.groupValues[2])) }
        italicRegex.findAll(text).forEach { tokens.add(InlineToken(it.range.first, it.range.last + 1, TokenType.ITALIC, it.groupValues[2])) }
        codeRegex.findAll(text).forEach { tokens.add(InlineToken(it.range.first, it.range.last + 1, TokenType.CODE, it.groupValues[1])) }

        tokens.sortBy { it.start }

        // Remove overlapping tokens (prefer bold over italic, code over both)
        val filtered = mutableListOf<InlineToken>()
        tokens.forEach { token ->
            if (filtered.none { it.overlaps(token) }) {
                filtered.add(token)
            }
        }
        filtered.sortBy { it.start }

        filtered.forEach { token ->
            if (token.start > currentIndex) {
                withStyle(style = SpanStyle(color = color)) {
                    append(text.substring(currentIndex, token.start))
                }
            }

            val tokenStyle = when (token.type) {
                TokenType.BOLD -> SpanStyle(
                    color = color,
                    fontWeight = FontWeight.Bold
                )
                TokenType.ITALIC -> SpanStyle(
                    color = color,
                    fontStyle = FontStyle.Italic
                )
                TokenType.CODE -> SpanStyle(
                    color = Color(0xFF4FC3F7),
                    fontFamily = FontFamily.Monospace,
                    fontSize = style.fontSize * 0.9f
                )
            }

            withStyle(style = tokenStyle) {
                append(token.content)
            }
            currentIndex = token.end
        }

        if (currentIndex < text.length) {
            withStyle(style = SpanStyle(color = color)) {
                append(text.substring(currentIndex))
            }
        }
    }
}

private enum class TokenType { BOLD, ITALIC, CODE }

private data class InlineToken(
    val start: Int,
    val end: Int,
    val type: TokenType,
    val content: String
) {
    fun overlaps(other: InlineToken): Boolean {
        return (start < other.end && end > other.start)
    }
}
