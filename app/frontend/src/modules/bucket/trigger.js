const _UNITS = ['B', 'KB', 'MB', 'GB'];

// Formats a byte count for the bucket panel's file list (e.g. 1536 -> '1.5 KB').
export const formatFileSize = (bytes) => {
  const size = Number(bytes) || 0;
  if (size < 1024) return `${size} B`;

  let value = size;
  let unitIndex = 0;
  while (value >= 1024 && unitIndex < _UNITS.length - 1) {
    value /= 1024;
    unitIndex += 1;
  }
  return `${value.toFixed(1)} ${_UNITS[unitIndex]}`;
};
