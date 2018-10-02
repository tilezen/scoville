var map = L.map('map').setView([51.505, -0.09], 13);

L.tileLayer('http://{s}.tile.stamen.com/toner/{z}/{x}/{y}.png', {
    retina: true,
    subdomains: 'abcd',
    maxZoom: 16,
}).addTo(map);

L.tileLayer('http://localhost:{{ port }}/tiles/{z}/{x}/{y}.png', {
    attribution: 'Map data &copy; <a href="https://www.openstreetmap.org/">OpenStreetMap</a> contributors',
    maxZoom: 16,
    opacity: 0.5,
}).addTo(map);
