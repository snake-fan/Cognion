import ReactMarkdown from 'react-markdown'
import rehypeHighlight from 'rehype-highlight'
import rehypeKatex from 'rehype-katex'
import remarkMath from 'remark-math'

const CODE_SEGMENT_PATTERN = /(```[\s\S]*?```|~~~[\s\S]*?~~~|`[^`\n]*(?:`|$))/g

function normalizeLatexDelimiters(markdown) {
  if (!markdown) {
    return ''
  }

  return String(markdown)
    .split(CODE_SEGMENT_PATTERN)
    .map((segment, index) => {
      if (index % 2 === 1) {
        return segment
      }

      return segment
        .replace(/\\\[([\s\S]*?)\\\]/g, (_match, math) => `\n$$\n${math.trim()}\n$$\n`)
        .replace(/\\\(([\s\S]*?)\\\)/g, (_match, math) => `$${math}$`)
    })
    .join('')
}

function MarkdownContent({ children }) {
  return (
    <ReactMarkdown remarkPlugins={[remarkMath]} rehypePlugins={[rehypeKatex, rehypeHighlight]}>
      {normalizeLatexDelimiters(children)}
    </ReactMarkdown>
  )
}

export default MarkdownContent
