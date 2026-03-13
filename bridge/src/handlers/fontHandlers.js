import fs from 'fs'
import path from 'path'
import { registerFont } from 'canvas'
import { ValidationError } from '../utils/errorTypes.js'

const SUPPORTED_FONT_EXTS = new Set(['.ttf', '.otf', '.woff'])

// Track loaded fonts to avoid double-registration
const loadedFonts = new Map()

export async function loadFont({ file_path, family, style, weight } = {}) {
  if (!file_path) throw new ValidationError('file_path is required')
  if (!family)    throw new ValidationError('family is required')

  const ext = path.extname(file_path).toLowerCase()
  if (!SUPPORTED_FONT_EXTS.has(ext)) {
    throw new ValidationError(
      `Unsupported font type "${ext}". Supported: ${[...SUPPORTED_FONT_EXTS].join(', ')}`
    )
  }
  if (!fs.existsSync(file_path)) {
    throw new ValidationError(`Font file not found: ${file_path}`)
  }

  const key = `${family}|${style ?? ''}|${weight ?? ''}`
  if (loadedFonts.has(key)) {
    return loadedFonts.get(key)
  }

  const opts = { family }
  if (style)  opts.style  = style
  if (weight) opts.weight = weight

  registerFont(file_path, opts)

  const result = {
    file_path,
    family,
    style:  style  ?? 'normal',
    weight: weight ?? 'normal',
    registered: true,
  }

  loadedFonts.set(key, result)
  return result
}
