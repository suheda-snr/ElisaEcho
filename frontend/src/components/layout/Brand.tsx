/**
 * The logo file has generous transparent padding above and below the wordmark, so it is
 * sized by width and `object-cover` trims the empty top/bottom (the image file is unchanged).
 */
export function Brand() {
  return (
    <img
      src="/elisaecho_logo.png"
      alt="Elisa Echo"
      className="h-16 w-52 object-cover object-center"
      width={208}
      height={64}
    />
  )
}
