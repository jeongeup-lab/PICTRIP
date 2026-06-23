import { SEOUL_CITY_HALL } from "@/constants/map";

/** Build the self-contained HTML for the KakaoWebMap WebView. The Kakao JS SDK
 * is loaded with autoload=false and initialized in kakao.maps.load(). Markers
 * are CustomOverlays: ink teardrop pins + a blue current-location dot (the one
 * sanctioned color, S05 §1.2). Bridges via window.ReactNativeWebView. */
export function buildKakaoMapHtml(jsKey: string): string {
  const { lat, lng } = SEOUL_CITY_HALL;
  return `<!doctype html>
<html>
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no" />
<style>
  html,body,#map{margin:0;padding:0;width:100%;height:100%;overflow:hidden}
  .pin{width:18px;height:18px;background:#171719;border:2px solid #fff;border-radius:50% 50% 50% 0;transform:rotate(-45deg);box-shadow:0 1px 3px rgba(0,0,0,.3)}
  .me{width:16px;height:16px;background:#2D7DF6;border:3px solid #fff;border-radius:50%;box-shadow:0 0 0 6px rgba(45,125,246,.25)}
</style>
<script src="https://dapi.kakao.com/v2/maps/sdk.js?appkey=${jsKey}&autoload=false"></script>
</head>
<body>
<div id="map"></div>
<script>
  var map, pins = [], me = null;
  function post(type, payload){ if(window.ReactNativeWebView){ window.ReactNativeWebView.postMessage(JSON.stringify({type:type,payload:payload||{}})); } }
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
  kakao.maps.load(function(){
    map = new kakao.maps.Map(document.getElementById('map'), { center:new kakao.maps.LatLng(${lat},${lng}), level:6 });
    kakao.maps.event.addListener(map,'dragend',function(){ var c=map.getCenter(); post('center_changed',{lat:c.getLat(),lng:c.getLng()}); });
    post('ready');
  });
</script>
</body>
</html>`;
}
