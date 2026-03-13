import { createCanvas, getCanvasState, exportCanvas } from './canvasHandlers.js'
import { addLayer, clearLayer } from './layerHandlers.js'
import { createShape, updateShape, deleteShape, listShapes } from './shapeHandlers.js'
import { transformShape } from './transformHandlers.js'
import { createGroup } from './groupHandlers.js'
import { addImage, getImageInfo } from './imageHandlers.js'
import { loadFont } from './fontHandlers.js'
import { ActionNotFoundError } from '../utils/errorTypes.js'

const ACTION_MAP = {
  create_canvas:    createCanvas,
  get_canvas_state: getCanvasState,
  export_canvas:    exportCanvas,
  add_layer:        addLayer,
  clear_layer:      clearLayer,
  create_shape:     createShape,
  update_shape:     updateShape,
  delete_shape:     deleteShape,
  list_shapes:      listShapes,
  transform_shape:  transformShape,
  create_group:     createGroup,
  add_image:        addImage,
  get_image_info:   getImageInfo,
  load_font:        loadFont,
}

export async function dispatch(action, params) {
  const handler = ACTION_MAP[action]
  if (!handler) throw new ActionNotFoundError(action)
  return handler(params)
}
