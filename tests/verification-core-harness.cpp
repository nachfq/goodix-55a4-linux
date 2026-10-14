/* Synthetic features only. Links the actual LGPL SIGFM implementation and an
 * extracted fpi_print_sigfm_match body. No sensor, template file or USB context. */
#include "sigfm.hpp"
#include "img-info.hpp"
#include "binary.hpp"
#include <cassert>
#include <cmath>
#include <cstdlib>
#include <cstring>
#include <iostream>
#include <limits>
#include <memory>
#include <vector>
extern "C" int test_print_match(SigfmImgInfo *, SigfmImgInfo *, int, int, int);
static SigfmImgInfo fixture(bool distinguishable = true)
{
    SigfmImgInfo info;
    info.descriptors = cv::Mat::zeros(8,128,CV_32FC1);
    for(int i=0;i<8;i++) {
        info.keypoints.emplace_back(float((i%3)*13+2),float((i/3)*17+3),3.0f);
        info.descriptors.at<float>(i,i) = distinguishable ? 100.0f : 0.0f;
    }
    return info;
}
int main(int argc, char **argv)
{
    cv::setNumThreads(1);
    auto a=fixture(), b=fixture(false);
    if (argc == 2 && !std::strcmp(argv[1], "empty-probe")) {
        assert(test_print_match(&a,&a,1,0,72)==-1); return 0;
    }
    if (argc == 2 && !std::strcmp(argv[1], "truncated")) {
        int len; auto bytes=sigfm_serialize_binary(&a,&len); assert(bytes);
        auto parsed=sigfm_deserialize_binary(bytes,len-1);
        assert(!parsed); std::free(bytes); return 0;
    }
    assert(sigfm_match_score(&a,&a)>=72);
    assert(sigfm_match_score(&a,&b)==0);
    assert(test_print_match(&a,&a,1,1,72)==1);
    assert(test_print_match(&a,&b,1,1,72)==0);
    assert(test_print_match(&a,&a,0,1,72)==-1);
    assert(test_print_match(&a,&a,1,0,72)==-1);
    assert(test_print_match(&a,&a,1,2,72)==-1);
    assert(test_print_match(&a,&a,1,1,0)==-1);
    assert(test_print_match(nullptr,&a,1,1,72)==-1);
    assert(sigfm_match_score(nullptr,&a)==-1);
    auto empty=SigfmImgInfo{};
    assert(sigfm_match_score(&empty,&a)==-1);
    auto invalid=fixture(); invalid.keypoints.pop_back();
    assert(sigfm_match_score(&invalid,&a)==-1);
    invalid=fixture(); invalid.keypoints[0].pt.x=std::numeric_limits<float>::quiet_NaN();
    assert(sigfm_match_score(&invalid,&a)==-1);
    invalid=fixture(); invalid.descriptors.at<float>(0,0)=std::numeric_limits<float>::infinity();
    assert(sigfm_match_score(&invalid,&a)==-1);
    invalid=fixture(); invalid.keypoints[0].pt.x=1e9;
    assert(sigfm_match_score(&invalid,&a)==-1);
    int len=42;
    auto bytes=sigfm_serialize_binary(&a,&len); assert(bytes && len>0);
    auto parsed=sigfm_deserialize_binary(bytes,len); assert(parsed);
    assert(sigfm_match_score(parsed,&a)>=72);
    sigfm_free_info(parsed);
    for(int n=0;n<len;n++) assert(!sigfm_deserialize_binary(bytes,n));
    std::vector<unsigned char> trailing(bytes,bytes+len); trailing.push_back(0);
    assert(!sigfm_deserialize_binary(trailing.data(),trailing.size()));
    auto bad=std::vector<unsigned char>(bytes,bytes+len);
    std::size_t huge=std::numeric_limits<std::size_t>::max();
    std::memcpy(bad.data(),&huge,sizeof(huge));
    assert(!sigfm_deserialize_binary(bad.data(),bad.size()));
    auto header=sizeof(std::size_t)+8*28;
    for(int field=0;field<3;field++) {
        bad.assign(bytes,bytes+len); int value=std::numeric_limits<int>::max();
        std::memcpy(bad.data()+header+field*4,&value,4);
        assert(!sigfm_deserialize_binary(bad.data(),bad.size()));
    }
    std::free(bytes);
    assert(!sigfm_serialize_binary(&empty,&len) && len==0);
    assert(!sigfm_deserialize_binary(nullptr,4));
    assert(!sigfm_extract(nullptr,108,88));
    std::vector<SfmPix> blank(108*88,0);
    auto blank_info=sigfm_extract(blank.data(),108,88); assert(blank_info);
    assert(sigfm_keypoints_count(blank_info)==0); sigfm_free_info(blank_info);
    assert(!sigfm_extract(blank.data(),-1,88));
    bin::stream generic;
    auto matrix = cv::Mat::ones(7,9,CV_8UC1);
    generic << cv::Mat(matrix);
    cv::Mat restored; generic >> restored; assert(cv::norm(matrix,restored)==0);
    std::vector<int> values={3,5,1,7}, restored_values;
    generic << values; generic >> restored_values; assert(values==restored_values);
    std::vector<int> empty_values; generic << empty_values;
    generic >> restored_values; assert(restored_values.empty());
    auto original = new SigfmImgInfo{fixture()};
    auto copy=sigfm_copy_info(original); assert(copy);
    sigfm_free_info(original);
    assert(sigfm_match_score(copy,&a)>=72); sigfm_free_info(copy);
    std::cout << "PASS actual SIGFM: positive/negative score, wrapper guards, ownership, round-trip, every-prefix truncation, malformed shapes/counts, finite values, blank extraction\n";
}
