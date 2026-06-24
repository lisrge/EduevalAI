import SparkMD5 from 'spark-md5';

export async function computeFileMd5(file, { chunkSize = 5 * 1024 * 1024, onProgress } = {}) {
  if (!(file instanceof Blob)) {
    throw new Error('无效文件');
  }

  const size = Math.max(Number(file.size || 0), 0);
  if (size <= 0) {
    throw new Error('文件不能为空');
  }

  const safeChunkSize = Math.max(Number(chunkSize || 0), 1024 * 1024);
  const totalChunks = Math.max(Math.ceil(size / safeChunkSize), 1);
  const spark = new SparkMD5.ArrayBuffer();

  for (let index = 0; index < totalChunks; index += 1) {
    const start = index * safeChunkSize;
    const end = Math.min(start + safeChunkSize, size);
    const buffer = await file.slice(start, end).arrayBuffer();
    spark.append(buffer);
    if (typeof onProgress === 'function') {
      onProgress({
        loadedChunks: index + 1,
        totalChunks,
        percent: Math.round(((index + 1) / totalChunks) * 100),
      });
    }
  }

  return spark.end().toLowerCase();
}
