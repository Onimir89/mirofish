import { reactive } from 'vue'

const state = reactive({ files: null, requirement: '' })

export const setPendingUpload = (files, requirement) => {
  state.files = files
  state.requirement = requirement
}

export const getPendingUpload = () => ({
  files: state.files,
  requirement: state.requirement,
})

export const clearPendingUpload = () => {
  state.files = null
  state.requirement = ''
}
