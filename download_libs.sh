#!/usr/bin/env bash
set -uo pipefail

# Download front-end JS libraries into Django static dir.
# Run from repo root:  ./download_libs.sh

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
JS_LIB_DIR="$ROOT_DIR/indexerapp/static/js/lib"
JS_CDN_DIR="$ROOT_DIR/indexerapp/static/js/cdn"
CSS_LIB_DIR="$ROOT_DIR/indexerapp/static/css/lib"
CSS_CDN_DIR="$ROOT_DIR/indexerapp/static/css/cdn"
mkdir -p "$JS_LIB_DIR"
mkdir -p "$CSS_LIB_DIR"
mkdir -p "$JS_CDN_DIR"
mkdir -p "$CSS_CDN_DIR"

echo "Saving JS  libs into: $JS_LIB_DIR"  >&2
echo "Saving CSS libs into: $CSS_LIB_DIR" >&2

# Helper: download URL to target path if file missing or empty
fetch() {
      local url="$1"; shift
      local target="$1"; shift

      if [ -s "$target" ]; then
            echo "[skip] $target already exists" >&2
            return 0
      fi

      echo "[get ] $(basename "$target")  ←  $url" >&2
      if curl -L --show-error --silent "$url" -o "$target"; then
            if head -c 200 "$target" | grep -qi '<!doctype\|not found\|404'; then
                  echo "[warn] Got error page for $(basename \"$target\"), removing." >&2
                  rm -f "$target"
            fi
      else
            echo "[warn] curl failed for $(basename \"$target\")" >&2
            rm -f "$target"
      fi

      # If we downloaded a JS file, attempt to fetch its source map (common convention: add .map)
      case "$url" in
            *.js)
                  map_url="${url}.map"
                  map_target="${target}.map"
                  if [ ! -s "$map_target" ]; then
                        echo "[get ] $(basename \"$map_target\")  ←  $map_url" >&2
                        if curl -L --show-error --silent "$map_url" -o "$map_target"; then
                              if head -c 200 "$map_target" | grep -qi '<!doctype\|not found\|404'; then
                                    echo "[warn] Got error page for $(basename \"$map_target\"), removing." >&2
                                    rm -f "$map_target"
                              fi
                        else
                              rm -f "$map_target"
                        fi
                  fi
                  ;;
            *) ;;
      esac
}



########################
# Leaflet core + plugins
########################

# Leaflet 1.9.4 (as used in templates)
fetch "https://unpkg.com/leaflet@1.9.4/dist/leaflet.js" \
      "$JS_LIB_DIR/leaflet.js"
fetch "https://unpkg.com/leaflet@1.9.4/dist/leaflet.js.map" \
      "$JS_LIB_DIR/leaflet.js.map"

# MarkerCluster 1.5.3
fetch "https://unpkg.com/leaflet.markercluster@1.5.3/dist/leaflet.markercluster.js" \
      "$JS_LIB_DIR/leaflet.markercluster.js"
fetch "https://unpkg.com/leaflet.markercluster@1.5.3/dist/leaflet.markercluster.js.map" \
      "$JS_LIB_DIR/leaflet.markercluster.js.map"

# GeometryUtil
fetch "https://unpkg.com/leaflet-geometryutil@0.10.3/src/leaflet.geometryutil.js" \
      "$JS_LIB_DIR/leaflet.geometryutil.js"

# Arrowheads
fetch "https://unpkg.com/leaflet-arrowheads@1.4.0/src/leaflet-arrowheads.js" \
      "$JS_LIB_DIR/leaflet-arrowheads.js"

# Numbered markers (GitHub gist)
fetch "https://gist.githubusercontent.com/steflef/2711380/raw/a4532aeca4f70d1a056ccbc8d3d67e94a00bbc6d/leaflet_numbered_markers.js" \
      "$JS_LIB_DIR/leaflet_numbered_markers.js"

############
# Mirador 3
############

# Use "latest" as in existing templates; adjust if needed.
fetch "https://unpkg.com/mirador@latest/dist/mirador.min.js" \
      "$JS_LIB_DIR/mirador.min.js"
fetch "https://unpkg.com/mirador@latest/dist/mirador.min.js.map" \
      "$JS_LIB_DIR/mirador.min.js.map"

###############
# noUiSlider 15
###############

fetch "https://cdn.jsdelivr.net/npm/nouislider@15.7.1/dist/nouislider.js" \
      "$JS_LIB_DIR/nouislider.js"
fetch "https://cdn.jsdelivr.net/npm/nouislider@15.7.1/dist/nouislider.min.js" \
      "$JS_LIB_DIR/nouislider.min.js"

####################
# ONNX Runtime (ort)
####################

fetch "https://cdn.jsdelivr.net/npm/onnxruntime-web/dist/ort.min.js" \
      "$JS_LIB_DIR/ort.min.js"
fetch "https://cdn.jsdelivr.net/npm/onnxruntime-web/dist/ort.min.js.map" \
      "$JS_LIB_DIR/ort.min.js.map"

###########
# Bootstrap
###########

# Match version 5.2.3 used in templates.
fetch "https://cdn.jsdelivr.net/npm/bootstrap@5.2.3/dist/js/bootstrap.bundle.min.js" \
      "$JS_LIB_DIR/bootstrap.bundle.min.js"
fetch "https://cdn.jsdelivr.net/npm/bootstrap@5.2.3/dist/js/bootstrap.bundle.min.js.map" \
      "$JS_LIB_DIR/bootstrap.bundle.min.js.map"

#########
# Select2
#########

# Match 4.1.0-rc.0 used in static/page.html
fetch "https://cdn.jsdelivr.net/npm/select2@4.1.0-rc.0/dist/js/select2.min.js" \
      "$JS_LIB_DIR/select2.min.js"

# select2.multi-checkboxes (GitHub)
fetch "https://raw.githubusercontent.com/wasikuss/select2-multi-checkboxes/refs/heads/master/select2.multi-checkboxes.js" \
      "$JS_LIB_DIR/select2.multi-checkboxes.js"

##########
# Zoomist
##########

# Zoomist JS
fetch "https://cdn.jsdelivr.net/npm/zoomist@2/zoomist.umd.js" \
      "$JS_LIB_DIR/zoomist.umd.js"

##############
# CSS libraries
##############

# Leaflet core CSS (1.9.4)
fetch "https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" \
      "$CSS_LIB_DIR/leaflet.css"

# MarkerCluster CSS (1.5.3)
fetch "https://unpkg.com/leaflet.markercluster@1.5.3/dist/MarkerCluster.css" \
      "$CSS_LIB_DIR/MarkerCluster.css"
fetch "https://unpkg.com/leaflet.markercluster@1.5.3/dist/MarkerCluster.Default.css" \
      "$CSS_LIB_DIR/MarkerCluster.Default.css"

# Numbered markers CSS (GitHub gist)
fetch "https://gist.githubusercontent.com/steflef/2711380/raw/a4532aeca4f70d1a056ccbc8d3d67e94a00bbc6d/leaflet_numbered_markers.css" \
      "$CSS_LIB_DIR/leaflet_numbered_markers.css"

# noUiSlider CSS (15.7.1)
fetch "https://cdn.jsdelivr.net/npm/nouislider@15.7.1/dist/nouislider.css" \
      "$CSS_LIB_DIR/nouislider.css"
fetch "https://cdn.jsdelivr.net/npm/nouislider@15.7.1/dist/nouislider.min.css" \
      "$CSS_LIB_DIR/nouislider.min.css"

# Select2 CSS (4.1.0-rc.0, matching JS version)
fetch "https://cdn.jsdelivr.net/npm/select2@4.1.0-rc.0/dist/css/select2.min.css" \
      "$CSS_LIB_DIR/select2.min.css"

# Zoomist CSS
fetch "https://cdn.jsdelivr.net/npm/zoomist@2/zoomist.css" \
      "$CSS_LIB_DIR/zoomist.css"

##############################################
# LightGallery (js/lib/lightgallery/)
##############################################

echo "" >&2
echo "=== LightGallery ==" >&2

fetch "https://cdn.jsdelivr.net/npm/lightgallery@2.9.0/lightgallery.min.js" \
      "$JS_LIB_DIR/lightgallery/js/lightgallery.min.js"
fetch "https://cdn.jsdelivr.net/npm/lightgallery@2.9.0/plugins/thumbnail/lg-thumbnail.umd.js" \
      "$JS_LIB_DIR/lightgallery/plugins/lg-thumbnail.min.js"
fetch "https://cdn.jsdelivr.net/npm/lightgallery@2.9.0/plugins/zoom/lg-zoom.umd.js" \
      "$JS_LIB_DIR/lightgallery/plugins/lg-zoom.min.js"
fetch "https://cdn.jsdelivr.net/npm/lightgallery@2.9.0/css/lightgallery-bundle.min.css" \
      "$JS_LIB_DIR/lightgallery/css/lightgallery-bundle.min.css"

##############################################
# js/cdn  (used by page_local.html and others)
##############################################

echo "" >&2
echo "=== JS CDN ==" >&2

# jQuery
fetch "https://code.jquery.com/jquery-3.7.1.min.js" \
      "$JS_CDN_DIR/jquery-3.7.1.min.js"

# DataTables (jQuery plugin variant 1.13.7)
fetch "https://cdn.datatables.net/1.13.7/js/jquery.dataTables.js" \
      "$JS_CDN_DIR/jquery.dataTables.js"

# DataTables (standalone 2.0.3)
fetch "https://cdn.datatables.net/2.0.3/js/dataTables.min.js" \
      "$JS_CDN_DIR/dataTables.min.js"

# DataTables FixedHeader
fetch "https://cdn.datatables.net/fixedheader/4.0.1/js/dataTables.fixedHeader.min.js" \
      "$JS_CDN_DIR/dataTables.fixedHeader.min.js"

# simple-datatables
fetch "https://cdn.jsdelivr.net/npm/simple-datatables@7.1.2/dist/umd/simple-datatables.min.js" \
      "$JS_CDN_DIR/simple-datatables.min.js"

# PapaParse
fetch "https://cdnjs.cloudflare.com/ajax/libs/PapaParse/5.3.0/papaparse.min.js" \
      "$JS_CDN_DIR/papaparse.min.js"

# Alpine.js
fetch "https://cdnjs.cloudflare.com/ajax/libs/alpinejs/3.13.8/cdn.min.js" \
      "$JS_CDN_DIR/alpine.cdn.min.js"

# Axios
fetch "https://cdnjs.cloudflare.com/ajax/libs/axios/1.6.8/axios.min.js" \
      "$JS_CDN_DIR/axios.min.js"

# D3 v7
fetch "https://cdn.jsdelivr.net/npm/d3@7/dist/d3.min.js" \
      "$JS_CDN_DIR/d3.v7.min.js"

# FontAwesome (kit)
fetch "https://use.fontawesome.com/releases/v6.3.0/js/all.js" \
      "$JS_CDN_DIR/all.js"

# Select2 (copy for page_local.html)
fetch "https://cdn.jsdelivr.net/npm/select2@4.1.0-rc.0/dist/js/select2.min.js" \
      "$JS_CDN_DIR/select2.min.js"

# Bootstrap (copy for page_local.html)
fetch "https://cdn.jsdelivr.net/npm/bootstrap@5.2.3/dist/js/bootstrap.bundle.min.js" \
      "$JS_CDN_DIR/bootstrap.bundle.min.js"

# Mirador (copy for page_local.html)
fetch "https://unpkg.com/mirador@latest/dist/mirador.min.js" \
      "$JS_CDN_DIR/mirador.min.js"

# Leaflet (copy for page_local.html)
fetch "https://unpkg.com/leaflet@1.9.4/dist/leaflet.js" \
      "$JS_CDN_DIR/leaflet.js"

##############################################
# css/cdn  (used by page_local.html and others)
##############################################

echo "" >&2
echo "=== CSS CDN ==" >&2

# DataTables CSS (standalone 2.0.3)
fetch "https://cdn.datatables.net/2.0.3/css/dataTables.dataTables.min.css" \
      "$CSS_CDN_DIR/dataTables.dataTables.min.css"

# DataTables FixedHeader CSS
fetch "https://cdn.datatables.net/fixedheader/4.0.1/css/fixedHeader.dataTables.min.css" \
      "$CSS_CDN_DIR/fixedHeader.dataTables.min.css"

# simple-datatables CSS
fetch "https://cdn.jsdelivr.net/npm/simple-datatables@7.1.2/dist/style.min.css" \
      "$CSS_CDN_DIR/simple-datatables.style.min.css"

# Select2 CSS (copy for page_local.html)
fetch "https://cdn.jsdelivr.net/npm/select2@4.1.0-rc.0/dist/css/select2.min.css" \
      "$CSS_CDN_DIR/select2.min.css"

echo "" >&2
echo "All libraries processed." >&2
