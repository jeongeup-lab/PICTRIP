import type { Plan, ScheduleDay } from "@/features/plan/api";

export type RoutePoint = { lat: number; lng: number };

export function routePoints(days: ScheduleDay[]): RoutePoint[] {
  const points: RoutePoint[] = [];
  for (const day of days) {
    for (const slot of day.slots) {
      const spot = slot.place.spot;
      if (spot?.lat != null && spot.lng != null) points.push({ lat: spot.lat, lng: spot.lng });
    }
  }
  return points;
}

export function planRoutePoints(plan: Plan, focusedDay: number | null): RoutePoint[] {
  const days = focusedDay == null ? plan.days : plan.days.filter((d) => d.day === focusedDay);
  return routePoints(days);
}

export function buildPlanRouteHtml(jsKey: string): string {
  return `<!doctype html>
<html>
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no" />
<style>
  html,body,#map{margin:0;padding:0;width:100%;height:100%;overflow:hidden;background:#F7F7F8}
  .num{width:24px;height:24px;border-radius:50%;background:#171719;border:2px solid #fff;color:#fff;font:700 11px -apple-system,sans-serif;display:flex;align-items:center;justify-content:center;box-shadow:0 2px 6px rgba(23,23,25,.3)}
  .num.start{background:#03C75A}
  #msg{position:absolute;top:0;left:0;right:0;font:13px -apple-system,sans-serif;color:#9396A0;padding:16px;text-align:center;z-index:10}
</style>
</head>
<body>
<div id="map"></div>
<div id="msg"></div>
<script>
  var map, markers = [], line = null, pending = null;
  function post(type, payload){ if(window.ReactNativeWebView){ window.ReactNativeWebView.postMessage(JSON.stringify({type:type,payload:payload||{}})); } }
  function fail(msg, human){ document.getElementById('msg').textContent = human; post('error',{message:msg}); }
  function clear(){ markers.forEach(function(m){ m.setMap(null); }); markers = []; if(line){ line.setMap(null); line = null; } }
  function setRoute(points){
    if(!map){ pending = points; return; }
    clear();
    if(!points || points.length === 0) return;
    var bounds = new kakao.maps.LatLngBounds();
    var path = [];
    points.forEach(function(p, i){
      var pos = new kakao.maps.LatLng(p.lat, p.lng);
      bounds.extend(pos); path.push(pos);
      var el = document.createElement('div');
      el.className = 'num' + (i === 0 ? ' start' : '');
      el.textContent = String(i + 1);
      var ov = new kakao.maps.CustomOverlay({ position: pos, content: el, yAnchor: 0.5, zIndex: 2 });
      ov.setMap(map);
      markers.push(ov);
    });
    if(path.length > 1){
      line = new kakao.maps.Polyline({ path: path, strokeWeight: 3, strokeColor: '#171719', strokeOpacity: 0.75, strokeStyle: 'solid' });
      line.setMap(map);
      map.setBounds(bounds, 28, 28, 28, 28);
    } else {
      map.setCenter(path[0]);
      map.setLevel(5);
    }
  }
  function handle(e){ try{ var m = JSON.parse(e.data); if(m.cmd === 'setRoute') setRoute(m.points); }catch(_){} }
  document.addEventListener('message', handle);
  window.addEventListener('message', handle);
  function initMap(){
    try{
      map = new kakao.maps.Map(document.getElementById('map'), { center: new kakao.maps.LatLng(37.5665, 126.9780), level: 6 });
      map.setDraggable(false); map.setZoomable(false);
      document.getElementById('msg').textContent = '';
      if(pending){ setRoute(pending); pending = null; }
      post('ready');
    }catch(e){ fail('init-failed','경로를 표시할 수 없어요'); }
  }
  (function(){
    var key = ${JSON.stringify(jsKey)};
    if(!key){ fail('missing-js-key','지도 키가 설정되지 않았어요'); return; }
    var s = document.createElement('script');
    s.src = 'https://dapi.kakao.com/v2/maps/sdk.js?appkey=' + key + '&autoload=false';
    s.onerror = function(){ fail('sdk-load-failed','지도를 불러오지 못했어요'); };
    s.onload = function(){
      if(!window.kakao || !kakao.maps){ fail('sdk-invalid','지도 초기화에 실패했어요'); return; }
      kakao.maps.load(initMap);
    };
    document.head.appendChild(s);
  })();
</script>
</body>
</html>`;
}
