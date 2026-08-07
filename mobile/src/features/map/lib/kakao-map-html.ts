import { SEOUL_CITY_HALL } from "@/constants/map";

export const PIN_INK = "#2B3037";
export const PIN_STROKE = "#8D949E";
export const PIN_ACCENT = "#FF3B53";
export const PIN_RESULT = "#4A9EFF";

export const KOREA_BOUNDS = { swLat: 33.0, swLng: 124.5, neLat: 38.7, neLng: 132.0 };
export const KOREA_MAX_LEVEL = 12;

export const DARK_FILTER = "invert(1) hue-rotate(180deg)";

export interface KakaoMapOptions {
  interactive?: boolean;
  accentDot?: boolean;
  dark?: boolean;
}

export function buildKakaoMapHtml(jsKey: string, options: KakaoMapOptions = {}): string {
  const { interactive = true, accentDot = false, dark = false } = options;
  const { lat, lng } = SEOUL_CITY_HALL;
  const dotColor = accentDot ? PIN_ACCENT : "#fff";
  const darkCss = dark
    ? `#map{filter:${DARK_FILTER}}
       .pin,.sel,.me,#msg{filter:${DARK_FILTER}}
       .sel .pin{filter:none}`
    : "";
  const gestures = interactive
    ? `map.setMaxLevel(${KOREA_MAX_LEVEL});
       kakao.maps.event.addListener(map,'drag',clampCenter);
       kakao.maps.event.addListener(map,'zoom_changed',clampCenter);
       kakao.maps.event.addListener(map,'idle',function(){
         clampCenter();
         var c=map.getCenter(), b=map.getBounds(), sw=b.getSouthWest(), ne=b.getNorthEast();
         post('center_changed',{lat:c.getLat(),lng:c.getLng(),swLat:sw.getLat(),swLng:sw.getLng(),neLat:ne.getLat(),neLng:ne.getLng()});
       });`
    : `map.setDraggable(false); map.setZoomable(false);`;
  return `<!doctype html>
<html>
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no" />
<style>
  html,body,#map{margin:0;padding:0;width:100%;height:100%;overflow:hidden}
  .pin{width:28px;height:28px;background:${PIN_INK};border:2px solid ${PIN_STROKE};border-radius:50% 50% 50% 0;transform:rotate(-45deg);box-shadow:0 1px 3px rgba(0,0,0,.5);display:flex;align-items:center;justify-content:center}
  .pin .g{transform:rotate(45deg);width:15px;height:15px;display:flex;align-items:center;justify-content:center}
  .pin svg{width:15px;height:15px;display:block}
  .pin.anchor{width:34px;height:34px;border-color:#fff}
  .pin.anchor .g{width:18px;height:18px}
  .pin.anchor svg{width:18px;height:18px}
  .sel{position:relative;width:28px;height:28px;display:block}
  .sel .lab{position:absolute;top:30px;left:50%;transform:translateX(-50%);font:700 11px -apple-system,sans-serif;color:#F4F5F7;background:rgba(20,22,26,.88);border-radius:5px;padding:2px 7px;box-shadow:0 1px 4px rgba(0,0,0,.4);white-space:nowrap}
  .me{width:16px;height:16px;background:#4A9EFF;border:3px solid #fff;border-radius:50%;box-shadow:0 0 0 6px rgba(74,158,255,.25)}
  #msg{position:absolute;top:0;left:0;right:0;font:14px -apple-system,sans-serif;color:#8a8a8e;padding:16px;text-align:center;z-index:10}
  ${darkCss}
</style>
</head>
<body>
<div id="map"></div>
<div id="msg"></div>
<script>
  var map, pins = [], me = null, lastSpots = [], selectedId = null, anchorId = null;
  var GLYPHS = {
    attraction: '<path d="M3 18l5-8 3 4 3-5 4 9z"/>',
    food: '<path d="M6 3v8M9 3v8M7.5 11v10M16 3c-1.4 0-2 2.2-2 5s.6 4 2 4v9"/>',
    cafe: '<path d="M5 8h9v4a4 4 0 0 1-4 4H9a4 4 0 0 1-4-4zM14 9h2a2 2 0 0 1 0 4h-2M5 20h10"/>',
    leisure: '<path d="M3 9c2-2 4-2 6 0s4 2 6 0M3 15c2-2 4-2 6 0s4 2 6 0"/>',
    shopping: '<path d="M6 8h10l-1 12H7zM9 8V6a3 3 0 0 1 6 0v2"/>'
  };
  var DOT = ${JSON.stringify(dotColor)};
  var C = { ink:${JSON.stringify(PIN_INK)}, accent:${JSON.stringify(PIN_ACCENT)}, result:${JSON.stringify(PIN_RESULT)} };
  function glyphSvg(cat){
    var p = GLYPHS[cat] || '<circle cx="12" cy="12" r="3" fill="'+DOT+'" stroke="none"/>';
    return '<svg viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'+p+'</svg>';
  }
  var KOREA_BOUNDS = ${JSON.stringify(KOREA_BOUNDS)};
  function clampCenter(){
    if(!map) return;
    var c = map.getCenter(), lat = c.getLat(), lng = c.getLng();
    var la = Math.min(Math.max(lat, KOREA_BOUNDS.swLat), KOREA_BOUNDS.neLat);
    var ln = Math.min(Math.max(lng, KOREA_BOUNDS.swLng), KOREA_BOUNDS.neLng);
    if(la!==lat || ln!==lng) map.setCenter(new kakao.maps.LatLng(la,ln));
  }
  function post(type, payload){ if(window.ReactNativeWebView){ window.ReactNativeWebView.postMessage(JSON.stringify({type:type,payload:payload||{}})); } }
  function fail(msg, human, detail){ document.getElementById('msg').textContent = human; post('error',{message:msg, detail:detail||''}); }
  function clearPins(){ pins.forEach(function(o){ o.setMap(null); }); pins = []; }
  function setCenter(lat,lng){ if(map){ map.setCenter(new kakao.maps.LatLng(lat,lng)); } }
  function fitBounds(sw,ne,pad){ if(!map) return;
    var b = new kakao.maps.LatLngBounds(new kakao.maps.LatLng(sw.lat,sw.lng), new kakao.maps.LatLng(ne.lat,ne.lng));
    map.setBounds(b, pad.top||0, pad.right||0, pad.bottom||0, pad.left||0); }
  function esc(t){ return String(t==null?'':t).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }
  function pinEl(s, sel, isAnchor, anchored){
    var pin = document.createElement('div');
    pin.className = isAnchor ? 'pin anchor' : 'pin';
    pin.innerHTML = '<span class="g">'+glyphSvg(s.categoryGroup)+'</span>';
    if(isAnchor) pin.style.background = C.accent;
    else if(anchored) pin.style.background = C.result;
    if(!sel && !isAnchor) return pin;
    if(sel && !isAnchor) pin.style.background = C.accent;
    var wrap = document.createElement('div');
    wrap.className='sel';
    wrap.appendChild(pin);
    var lab = document.createElement('span');
    lab.className='lab';
    lab.textContent = s.title==null?'':String(s.title);
    wrap.appendChild(lab);
    return wrap;
  }
  function renderPins(){
    if(!map) return; clearPins();
    var anchored = anchorId != null;
    lastSpots.forEach(function(s){
      if(s.mapy==null||s.mapx==null) return;
      var id = String(s.contentId);
      var isAnchor = anchored && id===anchorId;
      var sel = selectedId!=null && id===selectedId;
      var el = pinEl(s, sel, isAnchor, anchored);
      var ov = new kakao.maps.CustomOverlay({ position:new kakao.maps.LatLng(s.mapy,s.mapx), content:el, yAnchor:1, zIndex: isAnchor?20:(sel?10:1) });
      ov.setMap(map);
      el.addEventListener('click', function(){ post('pin_tap',{contentId:s.contentId}); });
      pins.push(ov);
    });
  }
  function setPins(spots){ lastSpots = spots||[]; renderPins(); }
  function setSelected(id){ selectedId = (id==null?null:String(id)); renderPins(); }
  function setAnchor(id){ anchorId = (id==null?null:String(id)); renderPins(); }
  function setUserMarker(lat,lng){
    if(me){ me.setMap(null); me=null; }
    if(lat==null||!map) return;
    var el = document.createElement('div'); el.className='me';
    me = new kakao.maps.CustomOverlay({ position:new kakao.maps.LatLng(lat,lng), content:el });
    me.setMap(map);
  }
  function handle(e){ try{ var m = JSON.parse(e.data);
    if(m.cmd==='setCenter') setCenter(m.lat,m.lng);
    else if(m.cmd==='setPins') setPins(m.spots);
    else if(m.cmd==='setSelected') setSelected(m.contentId);
    else if(m.cmd==='setAnchor') setAnchor(m.contentId);
    else if(m.cmd==='setUserMarker') setUserMarker(m.lat,m.lng);
    else if(m.cmd==='fitBounds') fitBounds(m.sw,m.ne,m.pad||{});
  }catch(_){} }
  document.addEventListener('message', handle);
  window.addEventListener('message', handle);
  function initMap(){
    try{
      map = new kakao.maps.Map(document.getElementById('map'), { center:new kakao.maps.LatLng(${lat},${lng}), level:6, $scale:false });
      map.setCopyrightPosition(kakao.maps.CopyrightPosition.BOTTOMRIGHT, true);
      ${gestures}
      document.getElementById('msg').textContent='';
      post('ready');
    }catch(e){ fail('init-failed','지도를 표시할 수 없어요', String(e && e.message || e)); }
  }
  (function(){
    var key = ${JSON.stringify(jsKey)};
    if(!key){ fail('missing-js-key','KAKAO_JS_KEY 미설정 — .env에 EXPO_PUBLIC_KAKAO_JS_KEY 추가 필요'); return; }
    var s = document.createElement('script');
    s.src = 'https://dapi.kakao.com/v2/maps/sdk.js?appkey=' + key + '&autoload=false&libraries=clusterer,services';
    s.onerror = function(){
      fetch(s.src).then(function(r){ fail('sdk-load-failed','지도 SDK를 불러오지 못했어요','HTTP '+r.status); })
        .catch(function(e){ fail('sdk-load-failed','지도 SDK를 불러오지 못했어요',String(e)); });
    };
    s.onload = function(){
      if(!window.kakao || !kakao.maps){ fail('sdk-invalid','지도 SDK 초기화에 실패했어요'); return; }
      kakao.maps.load(initMap);
    };
    document.head.appendChild(s);
  })();
</script>
</body>
</html>`;
}
