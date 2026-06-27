import { SEOUL_CITY_HALL } from "@/constants/map";

/** Build the self-contained HTML for the KakaoWebMap WebView. The Kakao JS SDK
 * is loaded with autoload=false and initialized in kakao.maps.load(). Markers
 * are CustomOverlays: ink teardrop pins + a blue current-location dot (the one
 * sanctioned color, S05 §1.2). Bridges via window.ReactNativeWebView.
 *
 * When `interactive` is false the map is locked (no drag/zoom, no
 * center_changed events) so it can live inside a scrolling page (spot detail)
 * without fighting the page scroll. */
export function buildKakaoMapHtml(jsKey: string, interactive = true): string {
  const { lat, lng } = SEOUL_CITY_HALL;
  // 'idle' fires after the map settles from a drag, zoom, OR programmatic
  // setCenter — so the viewport bbox (sw/ne) is reported on every movement, not
  // just drags. The bbox drives "이 지역에서 검색" (query what the user sees).
  const gestures = interactive
    ? `kakao.maps.event.addListener(map,'idle',function(){
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
  .pin{width:18px;height:18px;background:#171719;border:2px solid #fff;border-radius:50% 50% 50% 0;transform:rotate(-45deg);box-shadow:0 1px 3px rgba(0,0,0,.3)}
  .me{width:16px;height:16px;background:#2D7DF6;border:3px solid #fff;border-radius:50%;box-shadow:0 0 0 6px rgba(45,125,246,.25)}
  #msg{position:absolute;top:0;left:0;right:0;font:14px -apple-system,sans-serif;color:#8a8a8e;padding:16px;text-align:center;z-index:10}
</style>
</head>
<body>
<div id="map"></div>
<div id="msg"></div>
<script>
  var map, pins = [], me = null;
  function post(type, payload){ if(window.ReactNativeWebView){ window.ReactNativeWebView.postMessage(JSON.stringify({type:type,payload:payload||{}})); } }
  function fail(msg, human){ document.getElementById('msg').textContent = human; post('error',{message:msg}); }
  function clearPins(){ pins.forEach(function(o){ o.setMap(null); }); pins = []; }
  function setCenter(lat,lng){ if(map){ map.setCenter(new kakao.maps.LatLng(lat,lng)); } }
  function setPins(spots){
    if(!map) return; clearPins();
    spots.forEach(function(s){
      if(s.mapy==null||s.mapx==null) return;
      var el = document.createElement('div'); el.className='pin';
      var ov = new kakao.maps.CustomOverlay({ position:new kakao.maps.LatLng(s.mapy,s.mapx), content:el, yAnchor:1 });
      ov.setMap(map);
      el.addEventListener('click', function(){ post('pin_tap',{contentId:s.contentId}); });
      pins.push(ov);
    });
  }
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
    else if(m.cmd==='setUserMarker') setUserMarker(m.lat,m.lng);
  }catch(_){} }
  document.addEventListener('message', handle);
  window.addEventListener('message', handle);
  function initMap(){
    try{
      map = new kakao.maps.Map(document.getElementById('map'), { center:new kakao.maps.LatLng(${lat},${lng}), level:6 });
      ${gestures}
      document.getElementById('msg').textContent='';
      post('ready');
    }catch(e){ fail('init-failed','지도를 표시할 수 없어요'); }
  }
  // Load the SDK dynamically so a domain-rejected / network failure surfaces
  // (a synchronous <script src> would fail silently → blank map).
  (function(){
    var key = ${JSON.stringify(jsKey)};
    if(!key){ fail('missing-js-key','KAKAO_JS_KEY 미설정 — .env에 EXPO_PUBLIC_KAKAO_JS_KEY 추가 필요'); return; }
    var s = document.createElement('script');
    s.src = 'https://dapi.kakao.com/v2/maps/sdk.js?appkey=' + key + '&autoload=false&libraries=clusterer,services';
    s.onerror = function(){ fail('sdk-load-failed','지도 SDK를 불러오지 못했어요'); };
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
