/* The hosted edition processes photos on the visitor's device; no local server required. */
let sourceUrl = null, selectedFile = null, resultUrl = null, demoReady = false;
let generation = 0, activeWorker = null;
const board = document.getElementById('photo-board');
const statusText = document.getElementById('extract-status');
const fileInput = document.getElementById('photo-input');
const extractButton = document.getElementById('extract-demo');
function resetExtraction() {
  generation++;
  if (activeWorker) activeWorker.terminate();
  activeWorker = null;
  resultUrl = null;
  extractButton.disabled = false;
  extractButton.textContent = '提取纹样';
  ['show-result', 'use-extracted'].forEach(id => document.getElementById(id).disabled = true);
  board.removeAttribute('aria-busy');
}
function showPhoto(result = false) {
  board.replaceChildren();
  const img = new Image();
  img.src = result ? resultUrl : sourceUrl;
  img.alt = result ? '提取后的透明纹样' : '上传的原始照片';
  if (result) img.style.background = 'conic-gradient(#ddd 25%,#fafafa 0 50%,#ddd 0 75%,#fafafa 0) 0 0 / 20px 20px';
  board.append(img);
  document.getElementById('show-source').classList.toggle('on', !result);
  document.getElementById('show-result').classList.toggle('on', result);
}
function showDemo(result = false) {
  board.innerHTML = '<span class="extract-badge">' + (result ? '预设结果 · 非模型推理' : '合成织物示例 · 非实拍') + '</span><div class="demo-photo ' + (result ? 'result' : '') + '">' + motif(1) + '</div>';
  document.getElementById('show-source').classList.toggle('on', !result);
  document.getElementById('show-result').classList.toggle('on', result);
}
document.getElementById('upload-photo').onclick = () => fileInput.click();
document.getElementById('replace-photo').onclick = () => fileInput.click();
document.getElementById('load-demo').onclick = () => {
  resetExtraction(); demoReady = true; selectedFile = null;
  showDemo();
  extractButton.textContent = '查看示例提取效果';
  document.getElementById('photo-name').textContent = '织物纹样 / 演示素材';
  document.getElementById('show-source').disabled = false;
  statusText.textContent = '示例使用预设纹样，可体验从提取到设计的流程。';
};
fileInput.onchange = async () => {
  const file = fileInput.files[0];
  fileInput.value = '';
  if (!file) return;
  if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type) || file.size > 15 * 1024 * 1024) {
    statusText.textContent = '请选择 15 MB 以内的 JPG、PNG 或 WebP 图片。'; return;
  }
  resetExtraction(); demoReady = false; selectedFile = null;
  const token = generation;
  extractButton.disabled = true;
  try {
    const bitmap = await createImageBitmap(file);
    const tooLarge = bitmap.width * bitmap.height > 24000000;
    bitmap.close();
    if (token !== generation) return;
    if (tooLarge) throw new Error('图片尺寸过大，请缩小至 2400 万像素以内。');
    if (sourceUrl) URL.revokeObjectURL(sourceUrl);
    selectedFile = file; sourceUrl = URL.createObjectURL(file);
    showPhoto();
    document.getElementById('photo-name').textContent = file.name;
    document.getElementById('show-source').disabled = false;
    extractButton.disabled = false;
    statusText.textContent = '照片已就绪。适合纯色背景；复杂背景请先裁剪。照片在当前设备处理，不上传。';
  } catch (error) {
    if (token === generation) statusText.textContent = error.message.includes('像素') ? error.message : '图片无法读取，请重新选择有效图片。';
  }
};
extractButton.onclick = async () => {
  if (demoReady) {
    showDemo(true);
    ['show-result', 'use-extracted'].forEach(id => document.getElementById(id).disabled = false);
    statusText.textContent = '预设示例已就绪，可带入工坊。'; return;
  }
  if (!selectedFile || activeWorker) return;
  const token = generation;
  extractButton.disabled = true;
  board.setAttribute('aria-busy', 'true');
  statusText.textContent = '正在分离背景，请稍候…';
  let bitmap;
  try {
    bitmap = await createImageBitmap(selectedFile);
    if (token !== generation) { bitmap.close(); return; }
    const ratio = Math.min(1, 1600 / Math.max(bitmap.width, bitmap.height));
    const canvas = document.createElement('canvas');
    canvas.width = Math.round(bitmap.width * ratio); canvas.height = Math.round(bitmap.height * ratio);
    const context = canvas.getContext('2d', {willReadFrequently: true});
    context.drawImage(bitmap, 0, 0, canvas.width, canvas.height); bitmap.close();
    const pixels = context.getImageData(0, 0, canvas.width, canvas.height);
    const worker = activeWorker = new Worker('extract-worker.js');
    const data = await new Promise((resolve, reject) => {
      const timeout = setTimeout(() => { worker.terminate(); reject(new Error('处理超时，请缩小图片后重试。')); }, 30000);
      worker.onmessage = ({data}) => { clearTimeout(timeout); data.error ? reject(new Error(data.error)) : resolve(data); };
      worker.onerror = () => { clearTimeout(timeout); reject(new Error('处理未完成，请刷新或更换图片重试。')); };
      worker.postMessage({pixels}, [pixels.data.buffer]);
    });
    worker.terminate();
    if (token !== generation) return;
    context.putImageData(data.pixels, 0, 0);
    resultUrl = canvas.toDataURL('image/png');
    showPhoto(true);
    ['show-result', 'use-extracted'].forEach(id => document.getElementById(id).disabled = false);
    statusText.textContent = data.preserved ? '已保留原图透明背景，可带入工坊。' : '基础背景分离完成，请检查细节。复杂照片尚需 AI 模型支持。';
  } catch (error) {
    if (token === generation) statusText.textContent = error.message;
  } finally {
    if (token === generation) {
      if (activeWorker) activeWorker.terminate();
      activeWorker = null; extractButton.disabled = false; board.removeAttribute('aria-busy');
    }
  }
};
document.getElementById('show-source').onclick = () => demoReady ? showDemo() : showPhoto();
document.getElementById('show-result').onclick = () => demoReady ? showDemo(true) : resultUrl && showPhoto(true);
document.getElementById('use-extracted').onclick = () => {
  state.photo = demoReady ? null : resultUrl;
  state.photoTint = false;
  if (demoReady) state.motif = 1;
  updateArt(); go('studio');
};

// Native SVG export uses the actual layout, rather than unrelated template coordinates.
document.getElementById('download').onclick = async () => {
  await Promise.all(document.getElementById('studio').getAnimations({subtree:true}).map(animation => animation.finished.catch(() => {})));
  const sheet = document.getElementById('sheet');
  const art = document.getElementById('sheet-art');
  const rect = sheet.getBoundingClientRect();
  const escape = value => value.replace(/[<>&"']/g, c => ({'<':'&lt;','>':'&gt;','&':'&amp;','"':'&quot;',"'":'&apos;'}[c]));
  const x = art.offsetLeft + art.offsetWidth / 2, y = art.offsetTop + art.offsetHeight / 2;
  const aw = art.offsetWidth, ah = art.offsetHeight;
  let artwork;
  if (state.photo) {
    const tint = state.photoTint ? '<filter id="tint" color-interpolation-filters="sRGB"><feFlood flood-color="' + state.color + '"/><feComposite in2="SourceGraphic" operator="in"/></filter>' : '';
    artwork = tint + `<image href="${state.photo}" x="${-aw/2}" y="${-ah/2}" width="${aw}" height="${ah}" preserveAspectRatio="xMidYMid meet" ${state.photoTint ? 'filter="url(#tint)"' : ''}/>`;
  } else {
    artwork = motif(state.motif).replace('<svg ', `<svg x="${-aw/2}" y="${-ah/2}" width="${aw}" height="${ah}" `).replaceAll('currentColor', state.color).replaceAll('var(--paper,#f5f2ea)', getComputedStyle(sheet).getPropertyValue('--paper').trim());
  }
  const labels = ['sheet-title', 'sheet-sub'].map(id => {
    const el = id === 'sheet-sub' ? sheet.querySelector('.sheet-sub') : document.getElementById(id);
    const bounds = el.getBoundingClientRect(), css = getComputedStyle(el);
    return `<text x="${bounds.left-rect.left+bounds.width/2}" y="${bounds.top-rect.top+bounds.height/2}" dominant-baseline="central" text-anchor="middle" font-family="${escape(css.fontFamily)}" font-size="${css.fontSize}" letter-spacing="${css.letterSpacing}" fill="${css.color}">${escape(el.textContent)}</text>`;
  }).join('');
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${rect.width*3}" height="${rect.height*3}" viewBox="0 0 ${rect.width} ${rect.height}"><rect width="100%" height="100%" fill="${getComputedStyle(sheet).backgroundColor}"/><g transform="translate(${x} ${y}) scale(${state.scale/100}) rotate(${state.angle})">${artwork}</g>${labels}</svg>`;
  const url = URL.createObjectURL(new Blob([svg], {type:'image/svg+xml'}));
  const link = document.createElement('a'); link.href = url; link.download = '纹拾-' + state.format + '.svg'; link.click();
  setTimeout(() => URL.revokeObjectURL(url), 10000);
  const toast = document.getElementById('toast'); toast.textContent = '设计已导出为 SVG 图片'; toast.classList.add('show'); setTimeout(() => toast.classList.remove('show'), 2500);
};
