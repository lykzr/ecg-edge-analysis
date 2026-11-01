#include "hgb.h"
#include <math.h>
int ecg_hgb_probability(const float x[192], double p[3]) {
    if (!x || !p) return -1;
    for (unsigned i=0;i<192;i++) if (!isfinite(x[i])) return -1;
    for (unsigned c=0;c<3;c++) p[c]=hgb_baseline[c];
    for (unsigned t=0;t<192;t++) {
        uint32_t first=hgb_tree_offsets[t], end=hgb_tree_offsets[t+1], at=first;
        unsigned depth=0;
        for (;;) {
            if (at>=end || depth++>5) return -2;
            const HgbNode *n=&hgb_nodes[at];
            if (n->leaf) { p[t%3]+=n->value; break; }
            if (n->feature>=192) return -2;
            at=first+((double)x[n->feature]<=n->threshold?n->left:n->right);
        }
    }
    double max=p[0]; for(unsigned c=1;c<3;c++) if(p[c]>max) max=p[c];
    double sum=0;for(unsigned c=0;c<3;c++) {p[c]=exp(p[c]-max);sum+=p[c];}
    if (!(sum>0) || !isfinite(sum)) return -2;
    for(unsigned c=0;c<3;c++) p[c]/=sum;
    return 0;
}
