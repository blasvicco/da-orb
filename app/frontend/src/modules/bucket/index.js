// Libs imports
import { defineStore } from 'pinia';
import { ref } from 'vue';

// App imports
import AppAPI from '@/modules/api';

// Session-scoped file bucket state, shared by the bucket drawer and any other
// entry point that can add files (menu item, drag-and-drop onto the chat input).
// A single store keeps them in sync without threading refs through component trees.
export const useBucket = defineStore('bucket', () => {
  const files = ref([]);
  // Files picked/dropped before a session exists yet — a session is only created
  // once the first message is sent, so these wait here until setSessionId() sees
  // a real id and uploads them.
  const pendingFiles = ref([]);
  const uploading = ref(false);

  const refreshFiles = async (sessionId) => {
    if (!sessionId) {
      files.value = [];
      return;
    }
    const result = await AppAPI.Bucket.files(sessionId);
    if (!result?.errors) files.value = result;
  };

  const uploadFiles = async (sessionId, fileList) => {
    uploading.value = true;
    const results = await Promise.all(
      fileList.map((file) => AppAPI.Bucket.upload(sessionId, file)),
    );
    uploading.value = false;
    await refreshFiles(sessionId);
    return results.filter((result) => !result?.errors);
  };

  // Called whenever the active session id changes. Flushes any staged files the
  // moment a real session becomes available, otherwise just reloads the list.
  const setSessionId = async (sessionId) => {
    if (sessionId && pendingFiles.value.length) {
      const staged = pendingFiles.value;
      pendingFiles.value = [];
      await uploadFiles(sessionId, staged);
    } else {
      await refreshFiles(sessionId);
    }
  };

  const addFiles = async (sessionId, fileList) => {
    const selected = Array.from(fileList || []);
    if (!selected.length) return [];
    if (sessionId) {
      return uploadFiles(sessionId, selected);
    }
    pendingFiles.value = [...pendingFiles.value, ...selected];
    return [];
  };

  const deleteFile = async (fileId) => {
    const result = await AppAPI.Bucket.deleteFile(fileId);
    if (result?.errors) return result;
    files.value = files.value.filter((file) => file.id !== fileId);
    return result;
  };

  const downloadUrl = (fileId) => AppAPI.Bucket.downloadUrl(fileId);

  const removePendingFile = (index) => {
    pendingFiles.value = pendingFiles.value.filter((_, pos) => pos !== index);
  };

  return {
    addFiles,
    deleteFile,
    downloadUrl,
    files,
    pendingFiles,
    refreshFiles,
    removePendingFile,
    setSessionId,
    uploading,
  };
});
