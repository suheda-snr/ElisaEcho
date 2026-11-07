/**
 * The logo file has generous transparent padding above and below the wordmark, so it is
 * sized by width and `object-cover` trims the empty top/bottom (the image file is unchanged).
 */
export function Brand({ compact = false }: { compact?: boolean }) {
  return (
    <img
      src="/elisaecho_logo.png"
      alt="Elisa Echo"
      className={
        compact
          ? 'h-9 w-[7.5rem] object-cover object-center'
          : 'h-12 w-40 object-cover object-center'
      }
      width={compact ? 120 : 160}
      height={compact ? 36 : 48}
    />
  )
}
