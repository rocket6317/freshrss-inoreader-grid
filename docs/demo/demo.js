/* Fictional editorial demo. Real extension and native FreshRSS handlers. */
function initDemo() {
 const stream = document.querySelector('#stream');
 const text = (tag, value, className) => {
  const node = document.createElement(tag); node.textContent = value;
  if (className) node.className = className; return node;
 };
 for (const story of window.demoArticles) {
  const entry = document.createElement('div');
  entry.className = 'flux not_read' + (story.id === 2 ? ' favorite' : '');
  entry.id = 'flux_' + story.id;
  entry.dataset.entry = story.id;
  entry.dataset.link = 'https://example.invalid/story/' + story.id;
  const header = document.createElement('ul'); header.className = 'horizontal-list flux_header';
  header.dataset.websiteName = story.source;
  const titleItem = document.createElement('li'); titleItem.className = 'item titleAuthorSummaryDate';
  const link = text('a', story.title, 'item-element title'); link.href = entry.dataset.link;
  titleItem.append(link); header.append(titleItem);
  const content = document.createElement('article'); content.className = 'flux_content';
  const inner = document.createElement('div'); inner.className = 'content';
  const readerHeader = document.createElement('header');
  readerHeader.append(text('div', story.source + ' · ' + story.date, 'website'));
  const h1 = document.createElement('h1'); h1.className = 'title';
  const original = text('a', story.title, 'go_website'); original.href = entry.dataset.link;
  h1.append(original); readerHeader.append(h1);
  const body = document.createElement('div'); body.className = 'text';
  const meta = document.createElement('span'); meta.className = 'ig-entry-meta'; meta.hidden = true;
  Object.assign(meta.dataset, {source: story.source, image: '/demo/images/' + story.image,
   imageWidth: '1280', date: story.date, datetime: '2026-10-17T10:00:00Z'});
  const image = document.createElement('img'); image.src = meta.dataset.image;
  image.alt = 'Illustrative stock photograph; see demo photo credits';
  body.append(meta, image, ...story.paragraphs.map(p => text('p', p)));
  inner.append(readerHeader, body); content.append(inner);
  const footer = document.createElement('footer');
  const read = text('a', 'Mark read', 'read'); read.href = '/?c=entry&a=read&id=' + story.id;
  footer.append(read); content.append(footer);
  entry.append(header, content); stream.append(entry);
 }
 init_stream(stream);
 document.querySelector('#nav_menu_toggle_aside button').onclick = () => toggle_aside_click();
 document.dispatchEvent(new Event('freshrss:globalContextLoaded'));
}
if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', initDemo);
else initDemo();
