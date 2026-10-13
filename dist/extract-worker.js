self.onmessage = ({data: {pixels}}) => {
  try {
    const {width, height, data} = pixels;
    let transparent = 0;
    for (let i = 3; i < data.length; i += 4) if (data[i] < 240) transparent++;
    if (transparent > width * height * 0.01) {
      self.postMessage({pixels, preserved: true}, [data.buffer]); return;
    }
    const edge = [];
    const step = Math.max(1, Math.floor(Math.max(width, height) / 200));
    for (let x = 0; x < width; x += step) for (const y of [0, height-1]) edge.push((y*width+x)*4);
    for (let y = 0; y < height; y += step) for (const x of [0, width-1]) edge.push((y*width+x)*4);
    const bg = [0,1,2].map(c => edge.map(i => data[i+c]).sort((a,b)=>a-b)[Math.floor(edge.length/2)]);
    const distance = i => Math.hypot(data[i]-bg[0], data[i+1]-bg[1], data[i+2]-bg[2]);
    const clean = edge.filter(i => distance(i) < 45).length / edge.length;
    if (clean < 0.7) throw new Error('背景较复杂，暂时无法可靠分离。请换用纯色背景照片，或先裁剪纹样。');
    let foreground = 0, removed = 0;
    for (let i = 0; i < data.length; i += 4) {
      const alpha = Math.max(0, Math.min(1, (distance(i)-25)/35));
      data[i+3] = Math.round(data[i+3]*alpha);
      if (data[i+3] > 128) foreground++;
      if (data[i+3] < 20) removed++;
    }
    if (foreground < width*height*0.002 || removed < width*height*0.01) throw new Error('没有找到清晰的纹样与背景，请更换对比更明显的照片。');
    self.postMessage({pixels, preserved: false}, [data.buffer]);
  } catch (error) { self.postMessage({error: error.message}); }
};
