import React from 'react';

// Minimal, safe markdown renderer for agent replies (headings, bullets, numbered lists,
// **bold**, *italic*, `code`). Builds React elements only - never injects HTML.

// LLMs often emit narrow/non-breaking spaces and non-breaking hyphens; normalise them so
// words and numbers space out like normal text.
const normalise = (text: string): string =>
  text
    .replace(/[\u00A0\u2007\u2009\u202F]/g, ' ')
    .replace(/[\u2010\u2011]/g, '-')
    .replace(/\r\n?/g, '\n');

const renderInline = (text: string, keyPrefix: string): React.ReactNode[] =>
  text.split(/(\*\*[^*]+\*\*|`[^`]+`|\*[^*\s][^*]*\*)/g).filter(Boolean).map((part, i) => {
    const key = `${keyPrefix}-${i}`;
    if (part.startsWith('**') && part.endsWith('**') && part.length > 4) {
      return <strong key={key}>{part.slice(2, -2)}</strong>;
    }
    if (part.startsWith('`') && part.endsWith('`') && part.length > 2) {
      return (
        <code key={key} style={{ backgroundColor: '#E2E8F0', padding: '1px 5px', borderRadius: '4px', fontSize: '12px' }}>
          {part.slice(1, -1)}
        </code>
      );
    }
    if (part.startsWith('*') && part.endsWith('*') && part.length > 2) {
      return <em key={key}>{part.slice(1, -1)}</em>;
    }
    return <React.Fragment key={key}>{part}</React.Fragment>;
  });

const BULLET = /^\s*[-*•]\s+(.*)$/;
const NUMBERED = /^\s*\d+[.)]\s+(.*)$/;
const HEADING = /^\s*#{1,6}\s+(.*)$/;

export const AgentReply: React.FC<{ text: string }> = ({ text }) => {
  const lines = normalise(text).split('\n');
  const blocks: React.ReactNode[] = [];
  let i = 0;

  while (i < lines.length) {
    const line = lines[i];
    if (!line.trim()) { i++; continue; }

    const key = `b${i}`;
    if (BULLET.test(line) || NUMBERED.test(line)) {
      const ordered = NUMBERED.test(line);
      const matcher = ordered ? NUMBERED : BULLET;
      const items: string[] = [];
      while (i < lines.length && matcher.test(lines[i])) {
        items.push(lines[i].match(matcher)![1]);
        i++;
      }
      const Tag = ordered ? 'ol' : 'ul';
      blocks.push(
        <Tag key={key} style={{ margin: '4px 0 10px', paddingLeft: '20px', display: 'flex', flexDirection: 'column', gap: '3px' }}>
          {items.map((item, n) => <li key={`${key}-${n}`}>{renderInline(item, `${key}-${n}`)}</li>)}
        </Tag>
      );
      continue;
    }

    const heading = line.match(HEADING);
    if (heading) {
      blocks.push(
        <div key={key} style={{ fontWeight: 800, margin: '8px 0 4px', color: '#0F172A' }}>
          {renderInline(heading[1], key)}
        </div>
      );
      i++;
      continue;
    }

    // Paragraph: consecutive plain lines
    const para: string[] = [];
    // A line that opens with a bold label (e.g. "**Risk:** ...") starts its own block.
    while (i < lines.length && lines[i].trim() && !BULLET.test(lines[i]) && !NUMBERED.test(lines[i]) && !HEADING.test(lines[i])
           && !(para.length > 0 && /^\*\*/.test(lines[i].trim()))) {
      para.push(lines[i].trim());
      i++;
    }
    const joined = para.join(' ');

    // Inline enumeration such as "Facts: 1) a. 2) b. 3) c." -> intro + list
    const inline = joined.match(/^(.*?)\s*\b1[.)]\s+(.+?)\s+2[.)]\s+(.+)$/);
    if (inline) {
      const items = `1) ${inline[2]} 2) ${inline[3]}`.split(/\s+(?=\d+[.)]\s)/).map(s => s.replace(/^\d+[.)]\s+/, ''));
      blocks.push(
        <div key={key} style={{ margin: '0 0 10px' }}>
          {inline[1] && <div>{renderInline(inline[1], `${key}-h`)}</div>}
          <ol style={{ margin: '4px 0 0', paddingLeft: '20px', display: 'flex', flexDirection: 'column', gap: '3px' }}>
            {items.map((item, n) => <li key={`${key}-${n}`}>{renderInline(item, `${key}-${n}`)}</li>)}
          </ol>
        </div>
      );
      continue;
    }
    blocks.push(<p key={key} style={{ margin: '0 0 10px' }}>{renderInline(joined, key)}</p>);
  }

  return <div style={{ lineHeight: 1.55 }}>{blocks}</div>;
};
