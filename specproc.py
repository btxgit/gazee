import sqlite3
import os

if __name__ == '__main__':
#    with open('/tmp/out.txt', 'rb') as fd:
#        s = fd.read()
#    ll = s.split('\n')
#    otl = []
#    s = '''UPDATE all_comics SET width=?, height=?, ratio=? WHERE comicid=?;'''
#    
#    with sqlite3.connect('data/gazee_comics.db') as con:
#        
#        for l in ll:
#            if l.strip() == '':
#                continue
#            tl = l.strip().split(',')
#            id = int(tl[0].split('-')[0], 10)
#            w = int(tl[1], 10)
#            h = int(tl[2], 10)
#            ratio = (1.0) * w / h
#            otl.append( (w,h,ratio,id) )
#        
#        print "Committing %d records..." % len(otl)
#        con.executemany(s, otl)
#        con.commit()
    tgtw = 225
    tgth = 300
        
    with sqlite3.connect('data/gazee_comics.db') as con:
        sql = '''SELECT comicid, width, height, ratio FROM all_comics;'''
        for row in con.execute(sql):
            cid, w, h, ratio = row
            
            if w == 0 or h == 0:
                continue

            part = (cid // 512)
            
            if ratio >= 1.2:
                rot = 90
                tw = h
                h = w
                w = tw
                ratio = (1.0) * w / h
                print("convert data/cache/%d/%d-native.jpg -rotate 90 -thumbnail %dx%d data/cache/%d/%d-%dx%d.jpg" % (part, cid, tgtw, tgth, part, cid, tgtw, tgth))
#                continue
            else:
                rot = 0
                
#            print("%d  [ %d x %d ] (%.4f)" % (cid, w, h, ratio))
                
            h1 = tgth
            w1 = int(h1 * ratio)
            
            w2 = tgtw
            h2 = int(w2 / ratio)
#            print("Opt1: %d x %d   Opt2: %d x %d" % (w1, h1, w2, h2))

            if (w1 > tgtw):
                infn = "data/cache/%d/%d-%dx%d.jpg" % (part, cid, tgtw, tgth)
                ofn = "data/cache/%d/p%d-%dx%d.jpg" % (part, cid, tgtw, tgth)
#                print("convert data/cache/%d/p%d-%dx%d.jpg -rotate 90 -thumbnail %dx%d %s" % (part, cid, tgtw, tgth, tgtw, tgth, infn))
                pw = w2
                ph = h2
                fixh = tgth - ph
                origfixh = fixh

                if ((fixh %2) == 1):
                    fixh += 1
                
                fixwh = fixh // 2
                
#                print("w1, h1 (%d, %d)    w2, h2 (%d, %d)" % (w1, h1, w2, h2))
                
                if rot == 90 or not os.path.exists(ofn):
                    print("bash imageborder -s 0x%d -p 20 -e edge -b 2 %s %s" % (fixwh, infn, ofn))
            else:
                pw = w1
                ph = h1

                fixw = tgtw - pw
                origfixw = fixw
                
                if ((fixw % 2) == 1):
                    fixw += 1
                    
                fixwb = fixw//2
                ofn = "data/cache/%d/p%d-%dx%d.jpg" % (part, cid, tgtw, tgth)
                if rot == 90 or not os.path.exists(ofn):
                    print("bash imageborder -s %dx0 -p 20 -e edge -b 2 data/cache/%d/%d-300x400.jpg %s" % (fixwb, part, cid, ofn))
            
            
            print("echo %d..."  % cid)
