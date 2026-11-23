"""도시 인구와 위치 정보를 확인할 수 있는 표를 생성합니다.
주요 도시: UN WUP 2025 도시권 인구(cv.cm의 80개 도시 순위에 인용된 값).
좌표는 도시 중심의 근사 위치이며 인구 중심점은 아닙니다.
보조 도시의 인구는 상대적 분포를 위한 추정값으로 UN WUP 2025 수치가 아닙니다.
"""
from pathlib import Path
import csv
ROOT=Path(__file__).resolve().parents[1]
# 도시명 | 위도 | 경도 | 2025년 인구(명) | 배치 방향(도)
primary='''
Jakarta| -6.21|106.85|41913860|125
Dhaka|23.81|90.41|36585479|80
Tokyo|35.68|139.69|33412512|140
Delhi|28.61|77.21|30222405|65
Shanghai|31.23|121.47|29558908|100
Guangzhou|23.13|113.26|27563372|110
Cairo|30.04|31.24|25566102|0
Manila|14.60|120.98|24735305|0
Kolkata|22.57|88.36|22549738|130
Seoul|37.57|126.98|22490482|95
Karachi|24.86|67.01|21422590|30
Mumbai|19.07|72.88|20203056|20
São Paulo|-23.55|-46.63|18949790|120
Bangkok|13.76|100.50|18180280|120
Mexico City|19.43|-99.13|17734212|90
Beijing|39.90|116.41|17013303|115
Lahore|31.55|74.35|15156430|90
Istanbul|41.01|28.98|15014763|95
Moscow|55.75|37.62|14524753|65
Ho Chi Minh City|10.82|106.63|14052713|40
Buenos Aires|-34.60|-58.38|14017736|120
New York City|40.71|-74.01|13920148|45
Shenzhen|22.54|114.06|13878396|80
Bengaluru|12.97|77.59|13187098|60
Osaka|34.69|135.50|12964145|100
Lagos|6.52|3.38|12791699|90
Los Angeles|34.05|-118.24|12740420|130
Chennai|13.08|80.27|11153205|10
Kinshasa|-4.32|15.31|10943641|100
Bogotá|4.71|-74.07|10624315|35
Lima|-12.05|-77.04|10580241|20
London|51.51|-0.13|10416420|110
Rio de Janeiro|-22.91|-43.20|9500336|65
Paris|48.86|2.35|9381921|90
Hyderabad|17.38|78.49|9190795|20
Tehran|35.69|51.39|9174964|90
Taipei|25.03|121.56|9137000|30
Luanda|-8.84|13.23|9051000|50
Bandung|-6.92|107.61|8909104|50
Chicago|41.88|-87.63|8864000|100
Chengdu|30.66|104.07|8813000|90
Kuala Lumpur|3.14|101.69|8443731|75
Dar es Salaam|-6.79|39.21|7795114|40
Suzhou|31.30|120.59|7731101|80
Ahmedabad|23.03|72.58|7632408|35
Hangzhou|30.27|120.15|7500208|120
Xi'an|34.34|108.94|7444000|65
Hong Kong|22.32|114.17|7429000|105
Wuhan|30.59|114.30|7363548|60
Dongguan|23.02|113.75|7360000|90
Tianjin|39.08|117.20|7285342|65
Alexandria|31.20|29.92|7266957|95
Foshan|23.02|113.12|7236000|105
Nagoya|35.18|136.91|7146160|90
Johannesburg|-26.20|28.05|7077175|20
Chongqing|29.56|106.55|7071073|45
Shenyang|41.80|123.43|6921000|70
Riyadh|24.71|46.67|6916417|65
Surat|21.17|72.83|6908925|110
Surabaya|-7.26|112.75|6843503|130
Pune|18.52|73.86|6817951|110
Baghdad|33.31|44.37|6812000|20
Khartoum|15.50|32.56|6809355|30
Nanjing|32.06|118.80|6800676|85
Santiago|-33.45|-70.67|6726045|20
Addis Ababa|9.03|38.75|6706000|30
Madrid|40.42|-3.70|6497000|90
Harbin|45.75|126.65|6115000|85
Houston|29.76|-95.37|6115000|90
Dallas|32.78|-96.80|6099000|70
Toronto|43.65|-79.38|6082000|65
Miami|25.77|-80.19|6036000|20
Belo Horizonte|-19.92|-43.94|5972000|60
Singapore|1.35|103.82|5792000|85
Philadelphia|39.95|-75.17|5695000|25
Atlanta|33.75|-84.39|5572000|80
Fukuoka|33.59|130.40|5551000|65
Barcelona|41.39|2.17|5494000|55
Saint Petersburg|59.93|30.34|5383000|45
Qingdao|36.07|120.38|5381000|95
'''
# 상위 80개 도시 외의 보조 데이터입니다. 인구는 반올림한 상대적 참고값이며 검증된 UN 도시 추정치가 아닙니다.
secondary='''
Busan|35.18|129.07|3.3
Daegu|35.87|128.60|2.4
Daejeon|36.35|127.38|1.5
Gwangju|35.16|126.85|1.4
Ulsan|35.54|129.31|1.1
Jeju|33.50|126.53|0.5
Sapporo|43.06|141.35|2.0
Sendai|38.27|140.87|1.1
Hiroshima|34.39|132.46|1.2
Okayama|34.66|133.93|0.7
Kobe|34.69|135.20|1.5
Kyoto|35.01|135.77|1.5
Niigata|37.91|139.04|0.8
Kitakyushu|33.88|130.88|0.9
Naha|26.21|127.68|0.3
Dalian|38.91|121.61|4.0
Jinan|36.67|116.99|3.0
Changchun|43.82|125.32|3.0
Zhengzhou|34.75|113.63|4.0
Hefei|31.82|117.23|3.0
Changsha|28.23|112.94|4.0
Kunming|25.04|102.71|3.0
Xiamen|24.48|118.09|3.0
Ningbo|29.87|121.55|3.0
Wenzhou|27.99|120.70|2.5
Fuzhou|26.08|119.30|3.0
Nanning|22.82|108.32|2.5
Lanzhou|36.06|103.83|2.6
Urumqi|43.82|87.62|3.0
Shijiazhuang|38.04|114.50|3.0
Yinchuan|38.49|106.23|1.5
Taiyuan|37.87|112.55|3.0
Haikou|20.04|110.32|1.6
Tainan|22.99|120.20|1.2
Kaohsiung|22.63|120.30|2.7
Taichung|24.15|120.67|2.8
Hanoi|21.03|105.85|4.0
Da Nang|16.05|108.20|1.1
Nha Trang|12.24|109.19|0.5
Can Tho|10.04|105.79|0.9
Phnom Penh|11.56|104.93|2.3
Vientiane|17.98|102.63|0.9
Yangon|16.87|96.20|4.5
Mandalay|21.96|96.09|1.2
Medan|3.60|98.67|2.5
Semarang|-6.97|110.42|1.7
Makassar|-5.15|119.43|1.5
Yogyakarta|-7.80|110.36|1.2
Palembang|-2.99|104.76|1.6
Denpasar|-8.65|115.22|1.0
Cebu City|10.32|123.89|1.0
Davao|7.07|125.61|1.7
Iloilo City|10.72|122.56|0.5
Chittagong|22.36|91.78|3.0
Sylhet|24.89|91.87|0.7
Islamabad|33.69|73.06|1.1
Rawalpindi|33.60|73.05|2.1
Faisalabad|31.42|73.08|3.4
Peshawar|34.01|71.58|2.0
Multan|30.20|71.47|1.8
Jaipur|26.91|75.79|3.5
Lucknow|26.85|80.95|3.0
Kanpur|26.45|80.33|2.9
Patna|25.60|85.14|2.4
Varanasi|25.32|83.01|1.2
Bhopal|23.26|77.41|2.0
Indore|22.72|75.86|2.1
Nagpur|21.15|79.09|2.4
Kochi|9.93|76.27|2.1
Thiruvananthapuram|8.52|76.94|1.1
Visakhapatnam|17.69|83.22|1.7
Coimbatore|11.02|76.96|1.6
Guwahati|26.14|91.74|1.0
Colombo|6.93|79.86|2.5
Kandy|7.29|80.64|0.4
Kathmandu|27.72|85.32|1.5
Dubai|25.20|55.27|3.4
Abu Dhabi|24.45|54.37|1.7
Doha|25.29|51.53|2.4
Kuwait City|29.38|47.98|2.9
Manama|26.23|50.58|0.7
Muscat|23.59|58.41|1.5
Mecca|21.39|39.86|1.6
Medina|24.47|39.61|1.4
Jeddah|21.54|39.17|4.5
Tabriz|38.08|46.29|1.7
Isfahan|32.65|51.67|2.0
Shiraz|29.59|52.58|1.6
Mashhad|36.30|59.61|3.0
Ankara|39.93|32.86|5.0
Izmir|38.42|27.14|3.0
Antalya|36.90|30.69|1.2
Bursa|40.20|29.06|2.0
Adana|37.00|35.32|1.8
Baku|40.41|49.87|2.3
Tbilisi|41.72|44.79|1.2
Yerevan|40.18|44.51|1.0
Tashkent|41.30|69.28|2.9
Almaty|43.24|76.94|2.1
Astana|51.16|71.43|1.3
Bishkek|42.87|74.60|1.0
Dushanbe|38.56|68.78|1.0
Kabul|34.53|69.17|4.0
Herat|34.35|62.20|0.6
Hamburg|53.55|9.99|1.9
Berlin|52.52|13.40|3.8
Munich|48.14|11.58|1.5
Cologne|50.94|6.96|1.1
Frankfurt|50.11|8.68|0.8
Stuttgart|48.78|9.18|0.7
Düsseldorf|51.23|6.77|0.6
Essen|51.46|7.01|0.6
Dortmund|51.51|7.47|0.6
Leipzig|51.34|12.38|0.6
Dresden|51.05|13.74|0.6
Amsterdam|52.37|4.90|1.2
Rotterdam|51.92|4.48|0.7
The Hague|52.08|4.30|0.6
Brussels|50.85|4.35|1.2
Antwerp|51.22|4.40|0.6
Vienna|48.21|16.37|2.0
Prague|50.08|14.44|1.3
Budapest|47.50|19.04|1.7
Warsaw|52.23|21.01|1.8
Krakow|50.06|19.94|0.8
Wroclaw|51.11|17.03|0.7
Gdansk|54.35|18.65|0.5
Lodz|51.76|19.46|0.7
Zurich|47.38|8.54|0.5
Geneva|46.20|6.14|0.5
Milan|45.46|9.19|1.4
Rome|41.90|12.50|2.8
Naples|40.85|14.27|1.0
Turin|45.07|7.69|0.9
Florence|43.77|11.25|0.4
Bologna|44.49|11.34|0.4
Venice|45.44|12.33|0.3
Genoa|44.41|8.93|0.6
Marseille|43.30|5.37|0.9
Lyon|45.76|4.84|0.5
Toulouse|43.60|1.44|0.5
Bordeaux|44.84|-0.58|0.3
Lille|50.63|3.06|1.0
Nice|43.70|7.27|0.4
Nantes|47.22|-1.55|0.3
Birmingham|52.49|-1.89|1.1
Manchester|53.48|-2.24|2.7
Liverpool|53.41|-2.98|0.9
Leeds|53.80|-1.55|0.8
Glasgow|55.86|-4.25|0.6
Edinburgh|55.95|-3.19|0.5
Bristol|51.45|-2.59|0.5
Cardiff|51.48|-3.18|0.4
Dublin|53.35|-6.26|1.2
Lisbon|38.72|-9.14|2.2
Porto|41.16|-8.63|1.3
Valencia|39.47|-0.38|0.8
Seville|37.39|-5.99|0.7
Zaragoza|41.65|-0.89|0.7
Bilbao|43.26|-2.94|0.4
Malaga|36.72|-4.42|0.6
Athens|37.98|23.73|3.1
Thessaloniki|40.64|22.94|0.8
Sofia|42.70|23.32|1.2
Bucharest|44.43|26.10|1.8
Belgrade|44.81|20.46|1.4
Zagreb|45.81|15.98|0.8
Ljubljana|46.06|14.51|0.3
Sarajevo|43.86|18.41|0.3
Skopje|41.99|21.43|0.5
Tirana|41.33|19.82|0.5
Kyiv|50.45|30.52|2.9
Kharkiv|49.99|36.23|1.4
Odesa|46.48|30.73|1.0
Dnipro|48.46|35.05|1.0
Minsk|53.90|27.56|2.0
Riga|56.95|24.11|0.6
Tallinn|59.44|24.75|0.4
Vilnius|54.69|25.28|0.6
Helsinki|60.17|24.94|0.7
Stockholm|59.33|18.06|1.0
Gothenburg|57.71|11.97|0.6
Oslo|59.91|10.75|0.7
Bergen|60.39|5.32|0.3
Copenhagen|55.68|12.57|0.7
Aarhus|56.16|10.21|0.3
Reykjavik|64.14|-21.94|0.2
Kazan|55.80|49.11|1.3
Nizhny Novgorod|56.30|43.94|1.2
Yekaterinburg|56.84|60.60|1.5
Novosibirsk|55.03|82.92|1.6
Vladivostok|43.12|131.88|0.6
Omsk|54.99|73.37|1.1
Samara|53.19|50.10|1.2
Rostov-on-Don|47.23|39.72|1.1
Volgograd|48.71|44.51|1.0
Perm|58.01|56.23|1.0
Krasnoyarsk|56.02|92.87|1.2
Irkutsk|52.29|104.29|0.6
Ufa|54.74|55.97|1.1
Makhachkala|42.98|47.50|0.6
Cape Town|-33.92|18.42|4.0
Durban|-29.86|31.02|3.5
Pretoria|-25.75|28.23|2.0
Port Elizabeth|-33.96|25.61|1.2
Bloemfontein|-29.12|26.22|0.5
Nairobi|-1.29|36.82|4.5
Mombasa|-4.04|39.66|1.2
Kampala|0.32|32.58|1.6
Kigali|-1.95|30.06|1.2
Bujumbura|-3.38|29.36|0.6
Juba|4.85|31.58|0.5
Mogadishu|2.05|45.32|2.0
Abidjan|5.36|-4.01|5.0
Accra|5.56|-0.20|2.4
Kumasi|6.69|-1.63|2.0
Dakar|14.69|-17.44|2.5
Bamako|12.64|-8.00|2.5
Ouagadougou|12.37|-1.52|2.0
Conakry|9.64|-13.58|1.7
Freetown|8.48|-13.23|1.0
Monrovia|6.31|-10.80|1.1
Lomé|6.13|1.22|1.5
Cotonou|6.37|2.43|1.0
Niamey|13.51|2.11|1.3
Kano|12.00|8.52|4.0
Ibadan|7.40|3.90|3.6
Port Harcourt|4.78|7.00|1.9
Abuja|9.08|7.40|2.7
Kaduna|10.51|7.44|1.0
Benin City|6.34|5.63|1.5
Douala|4.05|9.70|3.0
Yaoundé|3.87|11.52|3.0
Brazzaville|-4.26|15.28|2.0
Lubumbashi|-11.66|27.48|2.0
Goma|-1.68|29.23|0.7
Lilongwe|-13.96|33.77|1.2
Blantyre|-15.78|35.00|0.8
Lusaka|-15.42|28.28|2.3
Ndola|-12.97|28.64|0.5
Harare|-17.83|31.05|1.6
Bulawayo|-20.15|28.58|0.7
Maputo|-25.97|32.58|1.1
Beira|-19.84|34.84|0.5
Antananarivo|-18.91|47.51|1.4
Port Louis|-20.16|57.50|0.2
Giza|30.01|31.21|1.7
Suez|29.97|32.55|0.7
Port Said|31.27|32.30|0.6
Aswan|24.09|32.90|0.3
Luxor|25.69|32.64|0.5
Tripoli|32.89|13.19|1.2
Benghazi|32.12|20.07|0.6
Tunis|36.81|10.18|2.4
Sfax|34.74|10.76|0.3
Algiers|36.75|3.04|3.0
Oran|35.70|-0.63|0.8
Constantine|36.37|6.61|0.5
Casablanca|33.59|-7.62|3.4
Rabat|34.02|-6.84|0.6
Fez|34.06|-4.98|1.1
Marrakesh|31.63|-8.00|0.9
Tangier|35.77|-5.81|1.0
Agadir|30.42|-9.60|0.5
Nouakchott|18.08|-15.98|1.2
New Orleans|29.95|-90.07|1.3
Washington DC|38.90|-77.04|3.0
Baltimore|39.29|-76.61|1.5
Boston|42.36|-71.06|4.8
Detroit|42.33|-83.05|4.0
Cleveland|41.50|-81.69|2.0
Pittsburgh|40.44|-79.99|2.3
Buffalo|42.89|-78.87|1.1
Charlotte|35.23|-80.84|2.6
Nashville|36.16|-86.78|1.9
Tampa|27.95|-82.46|3.0
Orlando|28.54|-81.38|2.4
Jacksonville|30.33|-81.66|1.0
Austin|30.27|-97.74|2.0
San Antonio|29.42|-98.49|2.2
San Diego|32.72|-117.16|2.5
San Francisco|37.77|-122.42|4.0
San Jose|37.34|-121.89|1.5
Sacramento|38.58|-121.49|2.1
Portland|45.52|-122.68|2.5
Seattle|47.61|-122.33|3.6
Denver|39.74|-104.99|2.8
Phoenix|33.45|-112.07|4.0
Las Vegas|36.17|-115.14|2.3
Minneapolis|44.98|-93.27|3.5
St Louis|38.63|-90.20|2.4
Kansas City|39.10|-94.58|2.1
Oklahoma City|35.47|-97.52|1.4
Salt Lake City|40.76|-111.89|1.2
Honolulu|21.31|-157.86|0.9
Anchorage|61.22|-149.90|0.3
Vancouver|49.28|-123.12|2.7
Montreal|45.50|-73.57|3.5
Ottawa|45.42|-75.70|1.0
Quebec City|46.81|-71.21|0.8
Calgary|51.05|-114.07|1.5
Edmonton|53.55|-113.49|1.3
Winnipeg|49.90|-97.14|0.8
Halifax|44.65|-63.57|0.4
Victoria|48.43|-123.37|0.4
Guadalajara|20.67|-103.35|5.0
Monterrey|25.69|-100.32|4.8
Puebla|19.04|-98.20|2.4
Tijuana|32.52|-117.04|1.9
Juarez|31.73|-106.49|1.5
Leon|21.12|-101.68|1.7
Querétaro|20.59|-100.39|1.1
Toluca|19.29|-99.66|1.2
Merida|20.97|-89.62|1.0
Veracruz|19.17|-96.13|0.6
Acapulco|16.85|-99.91|0.7
Cancun|21.16|-86.85|0.9
Tegucigalpa|14.07|-87.21|1.2
San Pedro Sula|15.50|-88.03|0.8
Guatemala City|14.63|-90.51|3.0
San Salvador|13.69|-89.19|1.2
Managua|12.13|-86.25|1.1
San Jose Costa Rica|9.93|-84.08|1.4
Panama City|8.98|-79.52|1.8
Havana|23.11|-82.37|2.1
Santo Domingo|18.49|-69.93|2.3
Santiago Dominican Republic|19.45|-70.69|0.7
Port-au-Prince|18.54|-72.34|2.4
Kingston|17.97|-76.79|0.6
San Juan|-| -|0
Caracas|10.48|-66.90|2.5
Maracaibo|10.64|-71.63|1.6
Valencia Venezuela|10.17|-68.00|1.2
Maracay|10.25|-67.60|0.8
Medellin|6.25|-75.57|2.5
Cali|3.45|-76.53|2.3
Barranquilla|10.96|-74.80|1.3
Cartagena Colombia|10.39|-75.48|1.0
Bucaramanga|7.12|-73.12|0.6
Quito|-0.18|-78.47|1.8
Guayaquil|-2.17|-79.92|2.5
Cuenca Ecuador|-2.90|-79.00|0.6
Arequipa|-16.40|-71.54|1.0
Trujillo Peru|-8.11|-79.03|1.0
Chiclayo|-6.77|-79.84|0.5
La Paz|-16.49|-68.12|0.9
Santa Cruz Bolivia|-17.78|-63.18|1.7
Cochabamba|-17.39|-66.16|0.7
Asuncion|-25.28|-57.63|0.5
Montevideo|-34.90|-56.16|1.3
Cordoba Argentina|-31.42|-64.18|1.5
Rosario Argentina|-32.96|-60.64|1.0
Mendoza Argentina|-32.89|-68.83|0.9
La Plata|-34.92|-57.95|0.7
Mar del Plata|-38.00|-57.56|0.6
Salta|-24.79|-65.41|0.6
Brasilia|-15.79|-47.88|3.0
Salvador|-12.98|-38.50|2.9
Fortaleza|-3.73|-38.52|2.7
Recife|-8.05|-34.88|2.8
Porto Alegre|-30.03|-51.22|1.5
Curitiba|-25.43|-49.27|1.9
Campinas|-22.91|-47.06|1.2
Manaus|-3.12|-60.02|2.2
Belém|-1.46|-48.50|1.5
Goiania|-16.68|-49.25|1.5
Natal|-5.79|-35.21|0.8
Joao Pessoa|-7.12|-34.86|0.8
Maceio|-9.66|-35.74|1.0
Vitoria|-20.32|-40.34|0.4
Florianopolis|-27.59|-48.55|0.5
Cuiaba|-15.60|-56.10|0.6
Campo Grande|-20.47|-54.62|0.8
Sao Luis|-2.53|-44.30|1.0
Teresina|-5.09|-42.80|0.9
Porto Velho|-8.76|-63.90|0.5
Sydney|-33.87|151.21|5.1
Melbourne|-37.81|144.96|5.0
Brisbane|-27.47|153.03|2.6
Perth|-31.95|115.86|2.1
Adelaide|-34.93|138.60|1.4
Canberra|-35.28|149.13|0.4
Hobart|-42.88|147.33|0.2
Darwin|-12.46|130.84|0.15
Newcastle Australia|-32.93|151.78|0.4
Gold Coast|-28.00|153.43|0.6
Auckland|-36.85|174.76|1.5
Wellington|-41.29|174.78|0.4
Christchurch|-43.53|172.63|0.4
Hamilton New Zealand|-37.78|175.28|0.2
Dunedin|-45.87|170.50|0.1
Suva|-18.14|178.44|0.1
Port Moresby|-9.47|147.16|0.4
Honiara|-9.43|159.95|0.08
Noumea|-22.27|166.45|0.1
'''
rows=[]
for line in primary.strip().splitlines():
 vals=[v.strip() for v in line.split('|')]
 assert len(vals)==5,line
 name,lat,lon,pop,ang=vals
 rows.append(dict(name=name,latitude=float(lat),longitude=float(lon),population=int(pop),scope='UN2025_urban_area',orientation=float(ang)))
for line in secondary.strip().splitlines():
 vals=[v.strip() for v in line.split('|')]
 if len(vals)!=4:raise ValueError(line)
 name,lat,lon,pop=vals
 if lat=='-':continue
 rows.append(dict(name=name,latitude=float(lat),longitude=float(lon),population=round(float(pop)*1e6),scope='supplemental_approximation',orientation=''))
with open(ROOT/'assets'/'cities.csv','w',encoding='utf-8',newline='') as f:
 w=csv.DictWriter(f,fieldnames=['name','latitude','longitude','population','scope','orientation'])
 w.writeheader();w.writerows(rows)
print('Total',len(rows),'UN',sum(r['scope']=='UN2025_urban_area' for r in rows),'supplemental',sum(r['scope']!='UN2025_urban_area' for r in rows))
for name in ['Tokyo','Seoul','Jakarta']:
 r=next(r for r in rows if r['name']==name)
 print(name,r['population'])
